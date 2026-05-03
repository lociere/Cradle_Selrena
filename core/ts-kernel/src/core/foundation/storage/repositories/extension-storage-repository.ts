import { DBManager } from '../db-manager';

type StorageRow = { value_json: string };

/**
 * 鎻掍欢娌欑 K/V 瀛樺偍浠撳簱銆?
 * 姣忎釜鎻掍欢鎷ユ湁鐙珛鐨勫懡鍚嶇┖闂达紙extension_id锛夛紝閿€煎潎浠?JSON 褰㈠紡鎸佷箙鍖栦簬 extension_storage 琛ㄣ€?
 */
export class ExtensionStorageRepository {
  constructor(private readonly extensionId: string) {}

  async get(key: string): Promise<unknown> {
    const row = DBManager.instance.db
      .prepare('SELECT value_json FROM extension_storage WHERE extension_id = ? AND key = ?')
      .get(this.extensionId, key) as StorageRow | undefined;

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
        'INSERT OR REPLACE INTO extension_storage (extension_id, key, value_json, updated_at) VALUES (?, ?, ?, ?)'
      )
      .run(this.extensionId, key, valueJson, now);
  }

  async delete(key: string): Promise<void> {
    DBManager.instance.db
      .prepare('DELETE FROM extension_storage WHERE extension_id = ? AND key = ?')
      .run(this.extensionId, key);
  }
}

