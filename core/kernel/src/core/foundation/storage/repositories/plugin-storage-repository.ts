import { DBManager } from '../db-manager';

type StorageRow = { value_json: string };

/**
 * 插件沙箱 K/V 存储仓库。
 * 每个插件拥有独立的命名空间（plugin_id），键值均以 JSON 形式持久化于 plugin_storage 表。
 */
export class PluginStorageRepository {
  constructor(private readonly pluginId: string) {}

  async get(key: string): Promise<unknown> {
    const row = DBManager.instance.db
      .prepare('SELECT value_json FROM plugin_storage WHERE plugin_id = ? AND key = ?')
      .get(this.pluginId, key) as StorageRow | undefined;

    if (!row) return null;
    try {
      return JSON.parse(row.value_json);
    } catch {
      return null;
    }
  }

  async set(key: string, value: unknown): Promise<void> {
    const valueJson = JSON.stringify(value);
    const now = new Date().toISOString();
    DBManager.instance.db
      .prepare(
        'INSERT OR REPLACE INTO plugin_storage (plugin_id, key, value_json, updated_at) VALUES (?, ?, ?, ?)'
      )
      .run(this.pluginId, key, valueJson, now);
  }

  async delete(key: string): Promise<void> {
    DBManager.instance.db
      .prepare('DELETE FROM plugin_storage WHERE plugin_id = ? AND key = ?')
      .run(this.pluginId, key);
  }
}
