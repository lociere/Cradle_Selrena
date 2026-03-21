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
  ChatMessageResponse,
  LifeHeartbeatRequest,
  LifeHeartbeatResponse,
  AgentPlanRequest,
  AgentPlanResponse,
  PerceptionCancelRequest,
  PerceptionMessageRequest,
  createIPCRequest,
  createTraceContext,
  CoreException,
  ErrorCode,
  KnowledgeInitRequest,
} from "@cradle-selrena/protocol";
import { ConfigManager } from "../../../infrastructure/config/config-manager";
import { IPCServer } from "../../../infrastructure/ipc-broker/ipc-server";
import { MemoryRepository } from "../../../infrastructure/storage/repositories/memory-repository";
import { getLogger } from "../../../infrastructure/logger/logger";
import { resolveRepoRoot, resolveLogDir } from "../../../infrastructure/utils/path-utils";

const logger = getLogger("python-manager");

/**
 * 解析 Python AI 层输出的单行日志并路由到 TS logger。
 *
 * 支持两种格式：
 *   1. 纯 JSON（structlog ProcessorFormatter → stdout）：
 *      {"level":"info","event":"...","module":"...","timestamp":"..."}
 *   2. stdlib logging 前缀格式（date prefix + JSON，通常来自 stderr）：
 *      "2026-01-01 12:00:00,000 [INFO] {"event":"...","level":"info",...}"
 *
 * 对于无法解析的非 JSON 行（如 Traceback 纯文本），视为 error 级别直接输出。
 */
// 匹配 Python stdlib logging 的 "DATE TIME,ms [LEVEL] " 前缀
const PYTHON_STDLIB_LOG_PREFIX_RE = /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3} \[(\w+)\] /;

function routePythonLogLine(line: string, fromStderr = false): void {
  const trimmed = line.trim();
  if (!trimmed) return;

  // 尝试剥离 "DATE TIME [LEVEL] " 前缀（Python stdlib logging 格式）
  const prefixMatch = PYTHON_STDLIB_LOG_PREFIX_RE.exec(trimmed);
  const stdlibLevel = prefixMatch ? prefixMatch[1].toLowerCase() : null;
  const jsonStr = prefixMatch ? trimmed.slice(prefixMatch[0].length) : trimmed;

  let parsed: Record<string, unknown>;
  try {
    parsed = JSON.parse(jsonStr) as Record<string, unknown>;
  } catch {
    // 无法解析为 JSON：如果是 stderr 且短小，可能是真实错误（Traceback 等）
    if (fromStderr) {
      logger.error(trimmed, { source: "python-ai" });
    } else {
      // stdout 上的非 JSON 信息降级为 debug，避免误报
      logger.debug(trimmed, { source: "python-ai" });
    }
    return;
  }

  // 优先使用 structlog 输出的 level 字段，fallback 到 stdlib prefix 中解析出的等级
  const level = String(parsed.level ?? stdlibLevel ?? "info").toLowerCase();
  const event = String(parsed.event ?? "");
  const meta: Record<string, unknown> = { source: "python-ai" };
  if (parsed.module)    meta.module    = parsed.module;
  if (parsed.timestamp) meta.timestamp = parsed.timestamp;
  // 透传其余业务字段（排除已提取的字段）
  const { level: _l, event: _e, module: _m, timestamp: _t, logger: _lg, ...rest } = parsed;
  Object.assign(meta, rest);

  switch (level) {
    case "debug":
      logger.debug(event, meta);
      break;
    case "warning":
    case "warn":
      logger.warn(event, meta);
      break;
    case "error":
    case "critical":
      logger.error(event, meta);
      break;
    default:
      logger.info(event, meta);
  }
}

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
  /** 逐行缓冲：子进程 data 事件可能携带不完整行 */
  private _stdoutLineBuffer: string = "";
  private _stderrLineBuffer: string = "";

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

      const repoRoot = resolveRepoRoot();

      const venvPythonPath = process.platform === "win32"
        ? path.resolve(repoRoot, ".venv", "Scripts", "python.exe")
        : path.resolve(repoRoot, ".venv", "bin", "python");
      const pythonEntryPath = path.resolve(repoRoot, "core", "cradle-selrena-core", "src", "selrena", "main.py");

      logger.debug("Python执行路径", { python_path: venvPythonPath, entry_path: pythonEntryPath });

      this._pythonProcess = spawn(venvPythonPath, [pythonEntryPath], {
        env: {
          ...process.env,
          SELRENA_IPC_BIND_ADDRESS: config.ipc.bind_address,
          SELRENA_CONFIG: JSON.stringify(config.ai),
          LOG_DIR: resolveLogDir(config.app.data_dir, config.app.log_dir),
          PYTHONUNBUFFERED: "1",
        },
        // 将 stdin 也设为 pipe 避免 Windows 下 inherit 导致 stdout 被路由到控制台
        stdio: ["pipe", "pipe", "pipe"],
      });

      this._pythonProcess.stdout?.on("data", (data: Buffer) => {
        this._stdoutLineBuffer += data.toString("utf-8");
        const lines = this._stdoutLineBuffer.split("\n");
        this._stdoutLineBuffer = lines.pop() ?? "";
        for (const line of lines) {
          routePythonLogLine(line, false);
        }
      });

      // stderr 同样使用 routePythonLogLine 解析，兼容 Python 日志写到 stderr 的情况
      // 真实的 Traceback / 非结构化错误仍会被识别并路由为 error 级别
      this._pythonProcess.stderr?.on("data", (data: Buffer) => {
        this._stderrLineBuffer += data.toString("utf-8");
        const lines = this._stderrLineBuffer.split("\n");
        this._stderrLineBuffer = lines.pop() ?? "";
        for (const line of lines) {
          routePythonLogLine(line, true);
        }
      });

      this._pythonProcess.on("exit", (code, signal) => {
        // 进程退出时刷新两路缓冲中的残余内容
        if (this._stdoutLineBuffer.trim()) {
          routePythonLogLine(this._stdoutLineBuffer, false);
          this._stdoutLineBuffer = "";
        }
        if (this._stderrLineBuffer.trim()) {
          routePythonLogLine(this._stderrLineBuffer, true);
          this._stderrLineBuffer = "";
        }
        logger.warn("Python AI层进程退出", { code, signal });
        this._isRunning = false;
        this._isReady = false;

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

      await this.waitForReady();
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
   * 等待 Python AI 层真正就绪：不仅是进程启动（PID 存在），
   * 而是等待 ZMQ DEALER 连接建立并收到第一条 IPC 消息（_lastClientId 非空）。
   * 只有这样，后续的 initAIConfig / initMemory / initKnowledge 才不会因
   * "未连接客户端" 而失败。
   */
  private async waitForReady(): Promise<void> {
    const maxWaitMs = 60_000;
    const pollIntervalMs = 300;
    const startAt = Date.now();

    logger.info("等待 Python AI 层 IPC 连接建立");

    return new Promise((resolve, reject) => {
      const check = () => {
        // 进程意外退出：快速失败，避免等满超时
        if (!this._pythonProcess || this._pythonProcess.killed) {
          return reject(new CoreException("Python 进程意外退出", ErrorCode.INFERENCE_ERROR));
        }

        // 最终检查：IPCServer 已收到来自 Python 的首条消息（_lastClientId 已设置）
        if (IPCServer.instance.isClientConnected) {
          logger.info("Python AI 层 IPC 连接已建立", {
            waited_ms: Date.now() - startAt,
          });
          return resolve();
        }

        if (Date.now() - startAt >= maxWaitMs) {
          return reject(new CoreException(
            `等待 Python AI 层 IPC 连接超时（>${maxWaitMs}ms）`,
            ErrorCode.INFERENCE_ERROR
          ));
        }

        setTimeout(check, pollIntervalMs);
      };

      // 延迟一个 tick 开始轮询，让进程有机会 spawn
      setTimeout(check, pollIntervalMs);
    });
  }

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

  private async initKnowledge(): Promise<void> {
    logger.info("开始初始化Python AI层知识库");
    const knowledgeBaseConfig = await ConfigManager.instance.loadKnowledgeBaseConfig();
    const payload: KnowledgeInitRequest = {
      knowledge_base: {
        version: knowledgeBaseConfig.version,
        retrieval: knowledgeBaseConfig.retrieval,
        entries: knowledgeBaseConfig.entries,
      },
    };

    const traceContext = createTraceContext();
    const request = createIPCRequest(
      IPCMessageType.KNOWLEDGE_INIT,
      traceContext.trace_id,
      payload
    );

    await this.sendRequest(request);
    logger.info("Python AI层知识库初始化完成", {
      knowledge_version: knowledgeBaseConfig.version,
      knowledge_entry_count: knowledgeBaseConfig.entries.length,
    });
  }

  /**
   * 向 Python AI 层发送请求并等待响应。
   * 委托给 IPCServer.sendRequest() 统一处理 RPC 协调（trace_id 关联、超时、并发安全）。
   */
  private async sendRequest(request: IPCRequest): Promise<IPCResponse> {
    if (!this._isRunning || !this._pythonProcess) {
      throw new CoreException("Python AI层未运行", ErrorCode.INFERENCE_ERROR);
    }

    // 使用 IPCServer 的 pendingRequests 机制处理并发安全的 RPC 调用
    const data = await IPCServer.instance.sendRequest<any>(
      request.type,
      request.payload,
      this._requestTimeoutMs
    );

    // 将裸数据包装为 IPCResponse，便于调用方统一处理
    return {
      type: IPCMessageType.SUCCESS_RESPONSE,
      trace_id: request.trace_id,
      success: true,
      data,
      payload: data,
    };
  }

  public async sendPerceptionMessage(request: PerceptionMessageRequest, traceId?: string): Promise<ChatMessageResponse> {
    if (!this._isReady) {
      throw new CoreException("Python AI层未就绪", ErrorCode.INFERENCE_ERROR);
    }

    const traceContext = createTraceContext({ trace_id: traceId });
    const ipcRequest = createIPCRequest(
      IPCMessageType.PERCEPTION_MESSAGE,
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

  public async cancelPerception(request: PerceptionCancelRequest): Promise<void> {
    if (!this._isReady) {
      return;
    }

    const traceContext = createTraceContext();
    const ipcRequest = createIPCRequest(
      IPCMessageType.PERCEPTION_CANCEL,
      traceContext.trace_id,
      request
    );

    await IPCServer.instance.sendToLatestClient(ipcRequest);
  }

  public async sendAgentPlan(request: AgentPlanRequest): Promise<AgentPlanResponse> {
    if (!this._isReady) {
      throw new CoreException("Python AI层未就绪", ErrorCode.INFERENCE_ERROR);
    }

    const traceContext = createTraceContext();
    const ipcRequest = createIPCRequest(
      IPCMessageType.AGENT_PLAN,
      traceContext.trace_id,
      request
    );

    const response = await this.sendRequest(ipcRequest);
    if (!response.success) {
      throw new CoreException(
        `Agent规划失败: ${response.error?.message}`,
        response.error?.code as ErrorCode || ErrorCode.INFERENCE_ERROR,
        traceContext.trace_id
      );
    }

    return response.data as AgentPlanResponse;
  }

  public async sendLifeHeartbeat(request: LifeHeartbeatRequest): Promise<LifeHeartbeatResponse> {
    if (!this._isReady) {
      throw new CoreException("Python AI层未就绪", ErrorCode.INFERENCE_ERROR);
    }

    const traceContext = createTraceContext();
    const ipcRequest = createIPCRequest(
      IPCMessageType.LIFE_HEARTBEAT,
      traceContext.trace_id,
      request
    );

    const response = await this.sendRequest(ipcRequest);
    if (!response.success) {
      logger.warn("生命心跳发送失败", { error: response.error?.message });
      throw new CoreException(`生命心跳失败: ${response.error?.message}`, ErrorCode.INFERENCE_ERROR);
    }

    return response.data as LifeHeartbeatResponse;
  }

  public async restart(): Promise<void> {
    logger.info("开始重启Python AI层");
    await this.stop();
    await new Promise((resolve) => setTimeout(resolve, 2000));
    await this.start();
    logger.info("Python AI层重启完成");
  }

  public async stop(): Promise<void> {
    if (!this._isRunning) {
      return;
    }

    logger.info("Python AI层开始停止");
    this._isRunning = false;
    this._isReady = false;

    if (this._pythonProcess && !this._pythonProcess.killed) {
      this._pythonProcess.kill("SIGTERM");
      await new Promise((resolve) => setTimeout(resolve, 5000));
      if (!this._pythonProcess.killed) {
        this._pythonProcess.kill("SIGKILL");
      }
    }

    this._pythonProcess = null;
    logger.info("Python AI层停止完成");
  }

  public get isReady(): boolean {
    return this._isReady && this._isRunning;
  }
}
