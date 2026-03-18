/**
 * 内核能力代理实现
 * 暴露给插件的内核能力，所有方法都有权限校验
 * 是插件与内核交互的唯一入口
 */
import {
  IKernelProxy,
  PluginSceneTranscriptEntry,
  Permission,
  hasPermission,
  ASRRecognizeRequest,
  ASRRecognizeResponse,
  ChatMessageResponse,
  PerceptionMessageRequest,
  TTSSynthesizeRequest,
  TTSSynthesizeResponse,
  LongTermMemoryFragment,
  EmotionState,
  SceneRoutingRequest,
  SceneRoutingResult,
  PluginException,
  ErrorCode,
} from "@cradle-selrena/protocol";
import { AIProxy } from "../../modules/ai/ai-proxy";
import { MemoryRepository } from "../../infrastructure/persistence/repositories/memory-repository";
import { ConfigManager } from "../../core/config/config-manager";
import { EventBus } from "../../core/event-bus/event-bus";
import { getLogger } from "../../core/observability/logger";
import { PluginStateLogger } from "../../core/observability/plugin-state-logger";
import { DBManager } from "../../infrastructure/persistence/db-manager";
import { AudioService } from "../../modules/audio/audio-service";
import { PluginSceneTranscriptService } from "./plugin-scene-transcript-service";
import { AttentionSessionManager } from "../../modules/attention/attention-session-manager";
import { SceneRoutingManager } from "../../modules/scene/scene-routing-manager";

const logger = getLogger("kernel-proxy");

/**
 * 内核能力代理实现类
 * 每个插件实例对应一个独立的代理实例，绑定插件的权限
 */
export class KernelProxyImpl implements IKernelProxy {
  private readonly _pluginId: string;
  private readonly _grantedPermissions: Permission[];
  private _eventSubscriptions: Map<string, Array<(event: any) => Promise<void>>> = new Map();

  constructor(pluginId: string, grantedPermissions: Permission[]) {
    this._pluginId = pluginId;
    this._grantedPermissions = grantedPermissions;
    logger.debug("内核代理实例创建完成", { plugin_id: pluginId, permissions: grantedPermissions });
  }

  /**
   * 校验权限
   */
  private checkPermission(requiredPermission: Permission): void {
    if (!hasPermission(requiredPermission, this._grantedPermissions)) {
      throw new PluginException(
        `插件 ${this._pluginId} 无权限: ${requiredPermission}`,
        ErrorCode.PLUGIN_PERMISSION_DENIED
      );
    }
  }

  // ====================== 日志能力 ======================
  log(level: string, message: string, meta: Record<string, unknown> = {}): void {
    const payload = { plugin_id: this._pluginId, ...meta };
    const normalized = level.toLowerCase();
    if (normalized === "debug") {
      logger.debug(message, payload);
      return;
    }
    if (normalized === "warn" || normalized === "warning") {
      logger.warn(message, payload);
      return;
    }
    if (normalized === "error" || normalized === "critical") {
      logger.error(message, payload);
      return;
    }
    logger.info(message, payload);
  }

  logState(
    level: "debug" | "info" | "warn" | "error" | "critical",
    stateKey: string,
    snapshot: unknown,
    message: string,
    meta: Record<string, unknown> = {}
  ): void {
    PluginStateLogger.instance.logIfChanged(this._pluginId, level, stateKey, snapshot, message, meta);
  }

  // ====================== 对话能力 ======================
  async resolveScene(request: SceneRoutingRequest): Promise<SceneRoutingResult> {
    return SceneRoutingManager.instance.resolve(request);
  }

  async ingestPerceptionMessage(request: PerceptionMessageRequest): Promise<ChatMessageResponse | null> {
    this.checkPermission(Permission.CHAT_SEND);
    const resolvedScene = SceneRoutingManager.instance.resolve({
      source: request.source,
      routing: request.routing,
    });

    const normalizedRequest: PerceptionMessageRequest = {
      ...request,
      scene_id: resolvedScene.scene_id,
    };

    logger.debug("插件调用注意力感知入口", {
      plugin_id: this._pluginId,
      scene_id: normalizedRequest.scene_id,
      source: normalizedRequest.source,
    });
    return AttentionSessionManager.instance.ingest(normalizedRequest);
  }

  async synthesizeSpeech(request: TTSSynthesizeRequest): Promise<TTSSynthesizeResponse> {
    this.checkPermission(Permission.NATIVE_AUDIO_TTS);
    logger.debug("插件调用 TTS", {
      plugin_id: this._pluginId,
      output_path: request.output_path,
    });
    return AudioService.instance.synthesizeSpeech(request);
  }

  async recognizeSpeech(request: ASRRecognizeRequest): Promise<ASRRecognizeResponse> {
    this.checkPermission(Permission.NATIVE_AUDIO_ASR);
    logger.debug("插件调用 ASR", {
      plugin_id: this._pluginId,
      audio_path: request.audio_path,
    });
    return AudioService.instance.recognizeSpeech(request);
  }

  async appendSceneTranscript(entry: PluginSceneTranscriptEntry): Promise<void> {
    this.checkPermission(Permission.MEMORY_WRITE);
    await PluginSceneTranscriptService.instance.append(this._pluginId, entry);
  }

  // ====================== 记忆能力 ======================
  async getRelevantMemories(query: string, limit: number = 5): Promise<LongTermMemoryFragment[]> {
    this.checkPermission(Permission.MEMORY_READ);
    logger.debug("插件调用获取相关记忆", { plugin_id: this._pluginId, query: query.slice(0, 20) });

    return MemoryRepository.instance.getRelevantMemories(query, limit);
  }

  async addMemory(memory: Omit<LongTermMemoryFragment, "memory_id" | "timestamp">): Promise<void> {
    this.checkPermission(Permission.MEMORY_WRITE);
    logger.debug("插件调用新增记忆", { plugin_id: this._pluginId, memory_type: memory.memory_type });

    MemoryRepository.instance.addMemory(memory);
  }

  async deleteMemory(memoryId: string): Promise<void> {
    this.checkPermission(Permission.MEMORY_DELETE);
    logger.warn("插件调用删除记忆", { plugin_id: this._pluginId, memory_id: memoryId });

    MemoryRepository.instance.deleteMemory(memoryId);
  }

  // ====================== 配置能力 ======================
  async getSelfConfig(): Promise<Record<string, any>> {
    this.checkPermission(Permission.CONFIG_READ_SELF);
    logger.debug("插件调用获取自身配置", { plugin_id: this._pluginId });

    const db = (await import("../../infrastructure/persistence/db-manager")).DBManager.instance.getDB();
    const row = db.prepare(`SELECT config FROM plugin_configs WHERE plugin_id = ?`).get(this._pluginId) as any;

    return row ? JSON.parse(row.config) : {};
  }

  async updateSelfConfig(config: Record<string, any>): Promise<void> {
    this.checkPermission(Permission.CONFIG_WRITE_SELF);
    logger.debug("插件调用更新自身配置", { plugin_id: this._pluginId });

    const db = (await import("../../infrastructure/persistence/db-manager")).DBManager.instance.getDB();
    db.prepare(`
      INSERT INTO plugin_configs (plugin_id, config, updated_at)
      VALUES (?, ?, CURRENT_TIMESTAMP)
      ON CONFLICT(plugin_id) DO UPDATE SET config = ?, updated_at = CURRENT_TIMESTAMP
    `).run(this._pluginId, JSON.stringify(config), JSON.stringify(config));
  }

  async getGlobalConfig(): Promise<Record<string, any>> {
    this.checkPermission(Permission.CONFIG_READ_GLOBAL);
    logger.debug("插件调用获取全局配置", { plugin_id: this._pluginId });

    return ConfigManager.instance.getConfig();
  }

  // ====================== 状态能力 ======================
  async getCurrentState(): Promise<{ isAwake: boolean; emotion: EmotionState; memoryCount: number }> {
    logger.debug("插件调用获取当前状态", { plugin_id: this._pluginId });

    const allMemories = MemoryRepository.instance.getAllMemories();
    return {
      isAwake: AIProxy.instance.isReady,
      emotion: {
        emotion_type: "calm",
        intensity: 0.2,
        trigger: "",
        timestamp: new Date().toISOString(),
      },
      memoryCount: allMemories.length,
    };
  }

  // ====================== 事件订阅能力 ======================
  async subscribeEvent(eventType: string, handler: (event: any) => Promise<void>): Promise<void> {
    this.checkPermission(Permission.EVENT_SUBSCRIBE);
    logger.debug("插件订阅事件", { plugin_id: this._pluginId, event_type: eventType });

    if (!this._eventSubscriptions.has(eventType)) {
      this._eventSubscriptions.set(eventType, []);
    }
    this._eventSubscriptions.get(eventType)!.push(handler);

    EventBus.instance.subscribe(eventType, async (event: any) => {
      const handlers = this._eventSubscriptions.get(eventType) || [];
      for (const h of handlers) {
        try {
          await h(event);
        } catch (err) {
          logger.error("插件事件处理失败", { plugin_id: this._pluginId, error: (err as Error).message });
        }
      }
    });
  }

  async unsubscribeEvent(eventType: string, handler: (event: any) => Promise<void>): Promise<void> {
    this.checkPermission(Permission.EVENT_SUBSCRIBE);
    const handlers = this._eventSubscriptions.get(eventType) || [];
    const idx = handlers.indexOf(handler);
    if (idx > -1) {
      handlers.splice(idx, 1);
    }
  }
}
