/**
 * IPC通信服务端
 * TS内核与Python AI层通信的唯一入口
 * 负责消息的接收、校验、处理、响应
 */
import * as zmq from "zeromq";
import {
  IPCMessageType,
  IPCRequest,
  IPCResponse,
  createSuccessResponse,
  createErrorResponse,
  ErrorCode,
  CoreException,
  createTraceContext,
  MemorySyncEvent,
  ShortTermMemorySyncEvent,
  StateSyncEvent,
  createIPCRequest,
} from "@cradle-selrena/protocol";
import { ConfigManager } from "../../core/config/config-manager";
import { getLogger } from "../../core/observability/logger";
import { EventBus } from "../../core/event-bus/event-bus";

const logger = getLogger("ipc-server");

const TRAFFIC_LOG_TYPES = new Set<IPCMessageType>([
  IPCMessageType.CONFIG_INIT,
  IPCMessageType.MEMORY_INIT,
  IPCMessageType.KNOWLEDGE_INIT,
  IPCMessageType.PERCEPTION_MESSAGE,
]);

/**
 * IPC请求处理器类型
 */
type IPCRequestHandler = (request: IPCRequest) => Promise<IPCResponse>;

/**
 * IPC通信服务端
 * 单例模式
 */
export class IPCServer {
  private static _instance: IPCServer | null = null;
  private _routerSocket: zmq.Router | null = null;
  private _pubSocket: zmq.Publisher | null = null;
  private _lastClientId: Buffer | null = null;
  private _isRunning: boolean = false;
  private _requestHandlers: Map<IPCMessageType, IPCRequestHandler> = new Map();
  private _messageHandler: (() => Promise<void>) | null = null;
  
  // 存储发出的请求，用于等待响应 (trace_id -> resolver)
  private _pendingRequests: Map<
    string,
    { resolve: (value: any) => void; reject: (reason?: any) => void; timer: NodeJS.Timeout }
  > = new Map();

  /** Python AI 层是否已建立首次 IPC 连接（收到至少一条消息）*/
  public get isClientConnected(): boolean {
    return this._lastClientId !== null;
  }

  /**
   * 获取单例实例
   */
  public static get instance(): IPCServer {
    if (!IPCServer._instance) {
      IPCServer._instance = new IPCServer();
    }
    return IPCServer._instance;
  }

  private constructor() {}

  private shouldLogTraffic(messageType: IPCMessageType): boolean {
    return TRAFFIC_LOG_TYPES.has(messageType);
  }

  /**
   * 启动IPC服务端
   */
  public async start(): Promise<void> {
    if (this._isRunning) {
      logger.warn("IPC服务端已在运行，跳过重复启动");
      return;
    }

    const config = ConfigManager.instance.getConfig();
    // Ensure bind address doesn't contain stray whitespace or line endings.
    let bindAddress = (config.ipc.bind_address || "").toString().trim();

    // Validate bind address format; fall back to a safe default if invalid.
    const bindMatch = /^tcp:\/\/([^:]+):(\d+)$/.exec(bindAddress);
    if (!bindMatch) {
      logger.warn("IPC bind_address 格式非法，使用默认地址", { bind_address: bindAddress });
      bindAddress = "tcp://127.0.0.1:8765";
    }

    logger.info("开始启动IPC服务端", { bind_address: bindAddress });

    try {
      // 创建Router套接字（处理请求/响应）
      this._routerSocket = new zmq.Router();
      await this._routerSocket.bind(bindAddress);
      logger.debug("Router套接字绑定成功", { bind_address: bindAddress });

      // 创建 Publisher 套接字（发布事件）
        // 创建Publisher套接字（发布事件）
        const match = /^tcp:\/\/([^:]+):(\d+)$/.exec(bindAddress);
        if (!match) {
          throw new CoreException(`不支持的IPC地址格式: ${bindAddress}`, ErrorCode.IPC_ERROR);
        }
        const host = match[1];
        const port = parseInt(match[2], 10);
        const pubAddress = `tcp://${host}:${port + 1}`;
      this._pubSocket = new zmq.Publisher();
      await this._pubSocket.bind(pubAddress);
      logger.debug("Publisher套接字绑定成功", { bind_address: pubAddress });

      // 注册默认处理器
      this.registerDefaultHandlers();

      // 启动消息循环
      this._isRunning = true;
      this.startMessageLoop();

      logger.info("IPC服务端启动成功", { bind_address: bindAddress, pub_address: pubAddress });
    } catch (error) {
      logger.error("IPC服务端启动失败", { error: (error as Error).message });
      throw new CoreException(`IPC服务端启动失败: ${(error as Error).message}`, ErrorCode.IPC_ERROR);
    }
  }

  /**
   * 注册默认请求处理器
   */
  private registerDefaultHandlers(): void {
    // 心跳处理器
    this.registerHandler(IPCMessageType.LIFE_HEARTBEAT, async (request) => {
      return createSuccessResponse(
        IPCMessageType.SUCCESS_RESPONSE,
        request.trace_id,
        { timestamp: new Date().toISOString() }
      );
    });

    // 日志事件处理器
    this.registerHandler(IPCMessageType.LOG, async (request) => {
      const logData = request.payload;
      logger.log(logData.level, logData.message, {
        ...logData.extra,
        trace_id: request.trace_id,
        from: "python-ai-core",
      });
      return createSuccessResponse(IPCMessageType.SUCCESS_RESPONSE, request.trace_id);
    });

    // 记忆同步事件处理器
    this.registerHandler(IPCMessageType.MEMORY_SYNC, async (request) => {
      const memory = request.payload?.memory ?? (request as any).memory;
      await EventBus.instance.publish(
        new MemorySyncEvent({ memory }, createTraceContext({ trace_id: request.trace_id }))
      );
      return createSuccessResponse(IPCMessageType.SUCCESS_RESPONSE, request.trace_id);
    });

    this.registerHandler(IPCMessageType.SHORT_TERM_MEMORY_SYNC, async (request) => {
      const fragment = request.payload?.fragment ?? (request as any).fragment;
      await EventBus.instance.publish(
        new ShortTermMemorySyncEvent({ fragment }, createTraceContext({ trace_id: request.trace_id }))
      );
      return createSuccessResponse(IPCMessageType.SUCCESS_RESPONSE, request.trace_id);
    });

    // 状态同步事件处理器
    this.registerHandler(IPCMessageType.STATE_SYNC, async (request) => {
      const state = request.payload?.state ?? (request as any).state;
      await EventBus.instance.publish(
        new StateSyncEvent({ state }, createTraceContext({ trace_id: request.trace_id }))
      );
      return createSuccessResponse(IPCMessageType.SUCCESS_RESPONSE, request.trace_id);
    });
  }

  /**
   * 注册请求处理器
   */
  public registerHandler(messageType: IPCMessageType, handler: IPCRequestHandler): void {
    this._requestHandlers.set(messageType, handler);
  }

  public unregisterHandler(messageType: IPCMessageType): void {
    this._requestHandlers.delete(messageType);
  }

  /**
   * 启动消息循环，处理客户端请求
   */
  private startMessageLoop(): void {
    if (!this._routerSocket || !this._isRunning) {
      return;
    }

    this._messageHandler = async () => {
      if (!this._routerSocket || !this._isRunning) {
        return;
      }

      try {
        // 接收消息：
        // - DEALER -> ROUTER 常见为 [clientId, message]
        // - 某些客户端可能携带空分隔帧 [clientId, empty, message]
        const frames = await this._routerSocket.receive();
        const clientId = frames[0];
        const messageBuffer = frames.length >= 3 ? frames[2] : frames[1];
        if (!clientId || !messageBuffer) {
          throw new CoreException("IPC消息帧格式非法", ErrorCode.IPC_ERROR);
        }
        // 记录最新连接的客户端 id，用于内核主动向 Python 发送请求
        this._lastClientId = clientId;
        const messageStr = messageBuffer.toString("utf-8");
        const request: IPCRequest = JSON.parse(messageStr);

        if (this.shouldLogTraffic(request.type)) {
          logger.info("收到IPC业务消息", {
            trace_id: request.trace_id,
            message_type: request.type,
            client_id: clientId.toString("hex"),
          });
        }

        // 检查是否为对我们发出请求的响应 (RPC Response)
        if (
          request.type === IPCMessageType.SUCCESS_RESPONSE ||
          request.type === IPCMessageType.ERROR_RESPONSE
        ) {
          const pending = this._pendingRequests.get(request.trace_id);
          if (pending) {
            if (request.type === IPCMessageType.SUCCESS_RESPONSE) {
              // 兼容 payload 和 data 字段
              const data = (request as any).data ?? request.payload;
              pending.resolve(data);
            } else {
              const errorInfo = (request as any).error ?? { message: "Unknown Error", code: "UNKNOWN" };
              pending.reject(new CoreException(errorInfo.message, errorInfo.code));
            }
            this._pendingRequests.delete(request.trace_id);
            // 响应已处理，进入下一轮循环
            if (this._isRunning) {
              setImmediate(this._messageHandler!);
            }
            return;
          }
        }

        const handler = this._requestHandlers.get(request.type);
        let response: IPCResponse;
        const noReplyTypes = new Set<IPCMessageType>([
          IPCMessageType.STATE_SYNC,
          IPCMessageType.MEMORY_SYNC,
          IPCMessageType.SHORT_TERM_MEMORY_SYNC,
          IPCMessageType.LOG,
          IPCMessageType.SUCCESS_RESPONSE,
          IPCMessageType.ERROR_RESPONSE,
        ]);

        if (!handler) {
          // 如果是RESPONSE且没被pending拦截（可能是超时了），则忽略
          if (
            request.type === IPCMessageType.SUCCESS_RESPONSE ||
            request.type === IPCMessageType.ERROR_RESPONSE
          ) {
            // 不做任何响应，直接结束本次处理
            if (this._isRunning) {
              setImmediate(this._messageHandler!);
            }
            return;
          }

          logger.warn("未找到IPC请求处理器", { message_type: request.type, trace_id: request.trace_id });
          response = createErrorResponse(
            IPCMessageType.ERROR_RESPONSE,
            request.trace_id,
            ErrorCode.IPC_ERROR,
            `未找到消息类型 ${request.type} 的处理器`
          );
        } else {
          // 执行处理器
          try {
            response = await handler(request);
          } catch (error) {
            logger.error("IPC请求处理器执行异常", {
              message_type: request.type,
              trace_id: request.trace_id,
              error: (error as Error).message,
            });
            response = createErrorResponse(
              IPCMessageType.ERROR_RESPONSE,
              request.trace_id,
              (error as CoreException).code || ErrorCode.IPC_ERROR,
              (error as Error).message
            );
          }
        }

        // 对事件/响应类消息不回包，避免形成无意义的应答回路。
        if (!noReplyTypes.has(request.type)) {
          await this._routerSocket.send([clientId, Buffer.from(JSON.stringify(response), "utf-8")]);
          if (this.shouldLogTraffic(request.type)) {
            logger.info("IPC业务响应发送完成", {
              trace_id: request.trace_id,
              message_type: request.type,
              success: response.success,
            });
          }
        }

      } catch (error) {
        if (this._isRunning) {
          logger.error("IPC消息处理异常", { error: (error as Error).message });
        }
      }

      // 继续循环
      if (this._isRunning) {
        setImmediate(this._messageHandler!);
      }
    };

    // 启动消息循环
    setImmediate(this._messageHandler);
  }

  /**
   * 向 Python AI 层发送请求并等待响应（pull-based RPC）。
   * 使用 pendingRequests 字典按 trace_id 关联，天然支持并发。
   */
  public async sendRequest<T = any>(type: IPCMessageType, payload: any = {}, timeoutMs: number = 30000): Promise<T> {
    if (!this._routerSocket || !this._isRunning || !this._lastClientId) {
      throw new CoreException("IPC服务端未运行或未连接客户端，无法发送请求", ErrorCode.IPC_ERROR);
    }

    // 生成 trace_id
    const traceContext = createTraceContext();
    const traceId = traceContext.trace_id;
    const request = createIPCRequest(type, traceId, payload);

    if (this.shouldLogTraffic(type)) {
      logger.info("发送IPC业务请求", {
        trace_id: traceId,
        message_type: type,
      });
    }

    return new Promise<T>((resolve, reject) => {
      // 设置超时定时器
      const timer = setTimeout(() => {
        if (this._pendingRequests.has(traceId)) {
          this._pendingRequests.delete(traceId);
          reject(new CoreException(`IPC请求超时 (${timeoutMs}ms)`, ErrorCode.IPC_TIMEOUT));
        }
      }, timeoutMs);

      // 注册 pending request
      this._pendingRequests.set(traceId, {
        resolve: (val) => {
          clearTimeout(timer);
          resolve(val);
        },
        reject: (err) => {
          clearTimeout(timer);
          reject(err);
        },
        timer,
      });

      // 发送消息
      // 注意：sendToLatestClient 是 fire-and-forget，我们在这里直接使用 _routerSocket 发送
      try {
        const buffer = Buffer.from(JSON.stringify(request), "utf-8");
        this._routerSocket!.send([this._lastClientId!, buffer]).catch((err) => {
          this._pendingRequests.get(traceId)?.reject(err);
          this._pendingRequests.delete(traceId);
        });
      } catch (error) {
        this._pendingRequests.get(traceId)?.reject(error);
        this._pendingRequests.delete(traceId);
      }
    });
  }

  /**
   * 向 Python AI 层 fire-and-forget 发送消息（不等待响应）。
   * 适用于直播弹幕等高并发场景。如需等待响应，请使用 sendRequest。
   * @deprecated 建议使用 sendRequest 以获得并发安全的 RPC 语义
   */
  public async sendToLatestClient(message: any): Promise<void> {
    if (!this._routerSocket || !this._isRunning || !this._lastClientId) {
      logger.warn("IPC服务端未运行或未连接客户端，无法发送消息");
      return;
    }

    try {
      await this._routerSocket.send([this._lastClientId, Buffer.from(JSON.stringify(message), "utf-8")]);
      if (this.shouldLogTraffic(message.type)) {
        logger.info("IPC业务消息发送到客户端", {
          message_type: message.type,
          trace_id: message.trace_id,
        });
      }
    } catch (error) {
      logger.error("IPC消息发送失败", { error: (error as Error).message });
    }
  }

  public async publishEvent(topic: string, data: Record<string, any>): Promise<void> {
    if (!this._pubSocket || !this._isRunning) {
      logger.warn("IPC服务端未运行，无法发布事件", { topic });
      return;
    }

    try {
      const message = JSON.stringify({ topic, data, timestamp: new Date().toISOString() });
      await this._pubSocket.send([topic, message]);
    } catch (error) {
      logger.error("IPC事件发布失败", { topic, error: (error as Error).message });
    }
  }

  /**
   * 停止IPC服务端，优雅停机
   */
  public async stop(): Promise<void> {
    if (!this._isRunning) {
      return;
    }

    logger.info("IPC服务端开始停止");
    this._isRunning = false;
    this._messageHandler = null;

    // 关闭套接字
    if (this._routerSocket) {
      this._routerSocket.close();
      this._routerSocket = null;
    }
    if (this._pubSocket) {
      this._pubSocket.close();
      this._pubSocket = null;
    }

    // 清空处理器
    this._requestHandlers.clear();
    logger.info("IPC服务端停止完成");
  }
}
