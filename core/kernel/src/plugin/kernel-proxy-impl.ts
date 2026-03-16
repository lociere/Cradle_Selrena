/**
 * 内核能力代理实现
 * 暴露给插件的内核能力，所有方法都有权限校验
 * 是插件与内核交互的唯一入口
 */
import {
  IKernelProxy,
  Permission,
  hasPermission,
  ChatMessageResponse,
  LongTermMemoryFragment,
  EmotionState,
  PluginException,
  ErrorCode,
} from "@cradle-selrena/protocol";
import { PythonAIManager } from "../ai-core/python-ai-manager";
import { MemoryRepository } from "../persistence/repositories/memory-repository";
import { ConfigManager } from "../config/config-manager";
import { EventBus } from "../event-bus/event-bus";
import { getLogger } from "../observability/logger";

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

  // ====================== 对话能力 ======================
  async sendChatMessage(
    userInput: string,
    sceneId: string,
    familiarity: number = 0
  ): Promise<ChatMessageResponse> {
    this.checkPermission(Permission.CHAT_SEND);
    logger.debug("插件调用发送聊天消息", { plugin_id: this._pluginId, scene_id: sceneId });

    return PythonAIManager.instance.sendChatMessage({
      user_input: userInput,
      scene_id: sceneId,
      familiarity: familiarity,
    });
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

    const db = (await import("../persistence/db-manager")).DBManager.instance.getDB();
    const row = db.prepare(`SELECT config FROM plugin_configs WHERE plugin_id = ?`).get(this._pluginId) as any;

    return row ? JSON.parse(row.config) : {};
  }

  async updateSelfConfig(config: Record<string, any>): Promise<void> {
    this.checkPermission(Permission.CONFIG_WRITE_SELF);
    logger.debug("插件调用更新自身配置", { plugin_id: this._pluginId });

    const db = (await import("../persistence/db-manager")).DBManager.instance.getDB();
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
      isAwake: PythonAIManager.instance.isReady,
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
