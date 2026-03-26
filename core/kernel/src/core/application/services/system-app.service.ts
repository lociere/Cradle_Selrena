import { ConfigManager } from "../../foundation/config/config-manager";
import { EventBus } from "../../foundation/event-bus/event-bus";
import { getLogger } from "../../foundation/logger/logger";
import { PluginStateLogger } from "../../foundation/logger/plugin-state-logger";
import { DBManager } from "../../foundation/storage/db-manager";
import { PluginLogLevel } from "@cradle-selrena/protocol";

export class SystemAppService {
  constructor(
    private configManager: ConfigManager,
    private eventBus: EventBus,
    private stateLogger: PluginStateLogger,
    private dbManager: DBManager
  ) {}

  public log(level: string, message: string, meta?: Record<string, unknown>): void {
    const logger = getLogger("plugin");
    logger.log(level, message, meta);
  }

  public logState(pluginId: string, level: PluginLogLevel, stateKey: string, snapshot: unknown, message: string, meta?: Record<string, unknown>): void {
    this.stateLogger.logIfChanged(pluginId, level, stateKey, snapshot, message, meta);
  }

  public async getSelfConfig(pluginId: string): Promise<Record<string, any>> {
    const db = this.dbManager.getDB();
    const row = db.prepare(`SELECT config FROM plugin_configs WHERE plugin_id = ?`).get(pluginId) as any;
    return row ? JSON.parse(row.config) : {};
  }

  public async updateSelfConfig(pluginId: string, config: Record<string, any>): Promise<void> {
    const db = this.dbManager.getDB();
    db.prepare(`
      INSERT INTO plugin_configs (plugin_id, config, updated_at)
      VALUES (?, ?, CURRENT_TIMESTAMP)
      ON CONFLICT(plugin_id) DO UPDATE SET config = ?, updated_at = CURRENT_TIMESTAMP
    `).run(pluginId, JSON.stringify(config), JSON.stringify(config));
  }

  public async getGlobalConfig(): Promise<Record<string, any>> {
    return this.configManager.getConfig();
  }

  public async subscribeEvent(eventType: string, handler: (event: any) => Promise<void>): Promise<void> {
    this.eventBus.subscribe(eventType, handler);
  }

  public async unsubscribeEvent(eventType: string, handler: (event: any) => Promise<void>): Promise<void> {
    this.eventBus.unsubscribe(eventType, handler);
  }
}