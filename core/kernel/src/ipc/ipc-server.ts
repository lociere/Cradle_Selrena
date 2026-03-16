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
  StateSyncEvent,
} from "@cradle-selrena/protocol";
import { ConfigManager } from "../config/config-manager";
import { getLogger } from "../observability/logger";
import { EventBus } from "../event-bus/event-bus";

const logger = getLogger("ipc-server");

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
  private _isRunning: boolean = false;
  private _requestHandlers: Map<IPCMessageType, IPCRequestHandler> = new Map();
  private _messageHandler: (() => Promise<void>) | null = null;

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

  /**
   * 启动IPC服务端
   */
  public async start(): Promise<void> {
    if (this._isRunning) {
      logger.warn("IPC服务端已在运行，跳过重复启动");
      return;
    }

    const config = ConfigManager.instance.getConfig();
    const bindAddress = config.ipc.bind_address;

    logger.info("开始启动IPC服务端", { bind_address: bindAddress });

    try {
      // 创建Router套接字（处理请求/响应）
      this._routerSocket = new zmq.Router();
      await this._routerSocket.bind(bindAddress);
      logger.debug("Router套接字绑定成功", { bind_address: bindAddress });

      // 创建Publisher套接字（发布事件）
      const pubAddress = bindAddress
        .replace("tcp://", "tcp://*:")
        .split(":")
        .slice(0, -1)
        .join(":") + ":" + (parseInt(bindAddress.split(":").pop()!) + 1);
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
      const { memory } = request.payload;
      await EventBus.instance.publish(
        new MemorySyncEvent({ memory }, createTraceContext({ trace_id: request.trace_id }))
      );
      return createSuccessResponse(IPCMessageType.SUCCESS_RESPONSE, request.trace_id);
    });

    // 状态同步事件处理器
    this.registerHandler(IPCMessageType.STATE_SYNC, async (request) => {
      const { state } = request.payload;
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
    logger.debug("IPC请求处理器注册成功", { message_type: messageType });
  }

  public unregisterHandler(messageType: IPCMessageType): void {
    this._requestHandlers.delete(messageType);
    logger.debug("IPC请求处理器注销成功", { message_type: messageType });
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
        // 接收消息（Router套接字接收的是 [clientId, empty, message]）
        const [clientId, , messageBuffer] = await this._routerSocket.receive();
        const messageStr = messageBuffer.toString("utf-8");
        const request: IPCRequest = JSON.parse(messageStr);

        logger.debug("收到IPC请求", {
          trace_id: request.trace_id,
          message_type: request.type,
          client_id: clientId.toString("hex"),
        });

        // 查找处理器
        const handler = this._requestHandlers.get(request.type);
        let response: IPCResponse;

        if (!handler) {
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

        // 发送响应
        await this._routerSocket.send([clientId, "", Buffer.from(JSON.stringify(response))]);
        logger.debug("IPC响应发送完成", { trace_id: request.trace_id, success: response.success });

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
   * 发布事件到Python AI层
   */
  public async publishEvent(topic: string, data: Record<string, any>): Promise<void> {
    if (!this._pubSocket || !this._isRunning) {
      logger.warn("IPC服务端未运行，无法发布事件", { topic });
      return;
    }

    try {
      const message = JSON.stringify({ topic, data, timestamp: new Date().toISOString() });
      await this._pubSocket.send([topic, message]);
      logger.debug("IPC事件发布完成", { topic });
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
