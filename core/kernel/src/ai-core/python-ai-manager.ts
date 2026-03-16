/**
 * Python AI层管理器
 * 负责Python子进程的启动、停止、生命周期管理、配置注入
 * 是TS内核与Python AI层交互的唯一入口
 */
import { spawn, ChildProcess } from "child_process";
import path from "path";
import {
  IPCMessageType,
  IPCRequest,
  IPCResponse,
  ChatMessageRequest,
  ChatMessageResponse,
  LifeHeartbeatResponse,
  createIPCRequest,
  createSuccessResponse,
  createTraceContext,
  CoreException,
  ErrorCode,
} from "@cradle-selrena/protocol";
import { ConfigManager } from "../config/config-manager";
import { IPCServer } from "../ipc/ipc-server";
import { MemoryRepository } from "../persistence/repositories/memory-repository";
import { getLogger } from "../observability/logger";
import { EventBus } from "../event-bus/event-bus";
import { AppStartedEvent } from "@cradle-selrena/protocol";

const logger = getLogger("python-ai-manager");

/**
 * Python AI层管理器
 * 单例模式
 */
export class PythonAIManager {
  private static _instance: PythonAIManager | null = null;
  private _pythonProcess: ChildProcess | null = null;
  private _isRunning: boolean = false;
  private _isReady: boolean = false;
  private _requestTimeoutMs: number = 30000;

  /**
   * 获取单例实例
   */
  public static get instance(): PythonAIManager {
    if (!PythonAIManager._instance) {
      PythonAIManager._instance = new PythonAIManager();
    }
    return PythonAIManager._instance;
  }

  private constructor() {}

  /**
   * 启动Python AI层子进程，初始化配置
   */
  public async start(): Promise<void> {
    if (this._isRunning) {
      logger.warn("Python AI层已在运行，跳过重复启动");
      return;
    }

    logger.info("开始启动Python AI层");
    const config = ConfigManager.instance.getConfig();
    this._requestTimeoutMs = config.ipc.request_timeout_ms;

    try {
      // 冻结核心配置，防止运行时修改
      ConfigManager.instance.freezeCoreConfig();

      // 确定Python执行路径（优先使用项目虚拟环境）
      const venvPythonPath = process.platform === "win32"
        ? path.resolve(process.cwd(), ".venv", "Scripts", "python.exe")
        : path.resolve(process.cwd(), ".venv", "bin", "python");
      const pythonEntryPath = path.resolve(process.cwd(), "core", "cradle-selrena-core", "src", "selrena", "main.py");

      logger.debug("Python执行路径", { python_path: venvPythonPath, entry_path: pythonEntryPath });

      // 启动Python子进程
      this._pythonProcess = spawn(venvPythonPath, [pythonEntryPath], {
        env: {
          ...process.env,
          SELRENA_IPC_BIND_ADDRESS: config.ipc.bind_address,
          SELRENA_CONFIG: JSON.stringify(config.ai),
          PYTHONUNBUFFERED: "1",
        },
        stdio: ["inherit", "pipe", "pipe"],
      });

      // 监听Python进程输出
      this._pythonProcess.stdout?.on("data", (data) => {
        logger.info("Python AI层输出", { output: data.toString("utf-8").trim() });
      });
      this._pythonProcess.stderr?.on("data", (data) => {
        logger.error("Python AI层错误输出", { error: data.toString("utf-8").trim() });
      });

      // 监听进程退出
      this._pythonProcess.on("exit", (code, signal) => {
        logger.warn("Python AI层进程退出", { code, signal });
        this._isRunning = false;
        this._isReady = false;

        // 非预期退出，自动重启
        if (code !== 0) {
          logger.error("Python AI层异常退出，正在自动重启");
          this.restart().catch(() => {
            logger.error("自动重启失败");
          });
        }
      });

      this._pythonProcess.on("error", (error) => {
        logger.error("Python AI层进程启动失败", { error: error.message });
        throw new CoreException(`Python进程启动失败: ${error.message}`, ErrorCode.INFERENCE_ERROR);
      });

      this._isRunning = true;

      // 等待Python进程就绪
      await this.waitForReady();
      // 初始化配置、记忆、知识库
      await this.initAIConfig();
      await this.initMemory();
      await this.initKnowledge();

      this._isReady = true;
      logger.info("Python AI层启动完成，已就绪");
    } catch (error) {
      logger.error("Python AI层启动失败", { error: (error as Error).message });
      await this.stop();
      throw error;
    }
  }

  /**
   * 等待Python AI层就绪
   */
  private async waitForReady(): Promise<void> {
    const maxWaitTime = 60000;
    const checkInterval = 1000;
    let waitedTime = 0;

    logger.info("等待Python AI层就绪");

    return new Promise((resolve, reject) => {
      const interval = setInterval(() => {
        waitedTime += checkInterval;

        if (waitedTime >= maxWaitTime) {
          clearInterval(interval);
          reject(new CoreException("Python AI层就绪等待超时", ErrorCode.INFERENCE_ERROR));
          return;
        }

        if (this._pythonProcess && this._pythonProcess.pid && !this._pythonProcess.killed) {
          clearInterval(interval);
          resolve();
        }
      }, checkInterval);
    });
  }

  /**
   * 发送配置初始化请求到Python AI层
   */
  private async initAIConfig(): Promise<void> {
    logger.info("开始初始化Python AI层配置");
    const config = ConfigManager.instance.getConfig();

    const traceContext = createTraceContext();
    const request = createIPCRequest(
      IPCMessageType.CONFIG_INIT,
      traceContext.trace_id,
      { config: config.ai }
    );

    await this.sendRequest(request);
    logger.info("Python AI层配置初始化完成");
  }

  /**
   * 发送记忆初始化请求到Python AI层
   */
  private async initMemory(): Promise<void> {
    logger.info("开始初始化Python AI层记忆");
    const allMemories = MemoryRepository.instance.getAllMemories();

    const traceContext = createTraceContext();
    const request = createIPCRequest(
      IPCMessageType.MEMORY_INIT,
      traceContext.trace_id,
      { memories: allMemories }
    );

    await this.sendRequest(request);
    logger.info("Python AI层记忆初始化完成", { memory_count: allMemories.length });
  }

  /**
   * 发送知识库初始化请求到Python AI层
   */
  private async initKnowledge(): Promise<void> {
    logger.info("开始初始化Python AI层知识库");
    const personaKnowledge = await ConfigManager.instance.loadPersonaKnowledge();

    const traceContext = createTraceContext();
    const request = createIPCRequest(
      IPCMessageType.KNOWLEDGE_INIT,
      traceContext.trace_id,
      { persona_knowledge: personaKnowledge, general_knowledge: [] }
    );

    await this.sendRequest(request);
    logger.info("Python AI层知识库初始化完成", { persona_knowledge_count: personaKnowledge.length });
  }

  /**
   * 发送请求到Python AI层，等待响应
   */
  private async sendRequest(request: IPCRequest): Promise<IPCResponse> {
    if (!this._isRunning || !this._pythonProcess) {
      throw new CoreException("Python AI层未运行", ErrorCode.INFERENCE_ERROR);
    }

    return new Promise((resolve, reject) => {
      let isResolved = false;

      // 超时处理
      const timeout = setTimeout(() => {
        if (!isResolved) {
          isResolved = true;
          reject(new CoreException(`Python AI层请求超时，trace_id: ${request.trace_id}`, ErrorCode.INFERENCE_ERROR));
        }
      }, this._requestTimeoutMs);

      // 注册临时处理器
      const responseHandler = async (response: IPCRequest): Promise<IPCResponse> => {
        if (response.trace_id === request.trace_id && !isResolved) {
          isResolved = true;
          clearTimeout(timeout);
          IPCServer.instance.unregisterHandler(request.type as IPCMessageType);
          resolve(response as unknown as IPCResponse);
        }
        return createSuccessResponse(IPCMessageType.SUCCESS_RESPONSE, request.trace_id);
      };

      IPCServer.instance.registerHandler(request.type as IPCMessageType, responseHandler);

      // 发布请求事件
      IPCServer.instance.publishEvent(request.type, request);
    });
  }

  /**
   * 发送聊天消息到AI层，获取回复
   */
  public async sendChatMessage(request: ChatMessageRequest): Promise<ChatMessageResponse> {
    if (!this._isReady) {
      throw new CoreException("Python AI层未就绪", ErrorCode.INFERENCE_ERROR);
    }

    const traceContext = createTraceContext();
    const ipcRequest = createIPCRequest(
      IPCMessageType.CHAT_MESSAGE,
      traceContext.trace_id,
      request
    );

    const response = await this.sendRequest(ipcRequest);
    if (!response.success) {
      throw new CoreException(
        `AI生成失败: ${response.error?.message}`,
        response.error?.code as ErrorCode || ErrorCode.INFERENCE_ERROR,
        traceContext.trace_id
      );
    }

    return response.data as ChatMessageResponse;
  }

  /**
   * 发送生命心跳到AI层，触发主动思维
   */
  public async sendLifeHeartbeat(): Promise<LifeHeartbeatResponse> {
    if (!this._isReady) {
      throw new CoreException("Python AI层未就绪", ErrorCode.INFERENCE_ERROR);
    }

    const traceContext = createTraceContext();
    const ipcRequest = createIPCRequest(
      IPCMessageType.LIFE_HEARTBEAT,
      traceContext.trace_id
    );

    const response = await this.sendRequest(ipcRequest);
    if (!response.success) {
      logger.warn("生命心跳发送失败", { error: response.error?.message });
      throw new CoreException(`生命心跳失败: ${response.error?.message}`, ErrorCode.INFERENCE_ERROR);
    }

    return response.data as LifeHeartbeatResponse;
  }

  /**
   * 重启Python AI层
   */
  public async restart(): Promise<void> {
    logger.info("开始重启Python AI层");
    await this.stop();
    // 等待2秒，确保资源完全释放
    await new Promise((resolve) => setTimeout(resolve, 2000));
    await this.start();
    logger.info("Python AI层重启完成");
  }

  /**
   * 停止Python AI层，优雅停机
   */
  public async stop(): Promise<void> {
    if (!this._isRunning) {
      return;
    }

    logger.info("Python AI层开始停止");
    this._isRunning = false;
    this._isReady = false;

    // 终止Python进程
    if (this._pythonProcess && !this._pythonProcess.killed) {
      this._pythonProcess.kill("SIGTERM");
      // 等待5秒，强制杀死
      await new Promise((resolve) => setTimeout(resolve, 5000));
      if (!this._pythonProcess.killed) {
        this._pythonProcess.kill("SIGKILL");
      }
    }

    this._pythonProcess = null;
    logger.info("Python AI层停止完成");
  }

  /**
   * 获取AI层运行状态
   */
  public get isReady(): boolean {
    return this._isReady && this._isRunning;
  }
}
