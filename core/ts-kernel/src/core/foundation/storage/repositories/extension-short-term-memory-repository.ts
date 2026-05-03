import { randomUUID } from 'node:crypto';
import type { ExtensionMemoryEntry, ExtensionMemoryEntryInput, IExtensionShortTermMemory } from '@cradle-selrena/protocol';
import { DBManager } from '../db-manager';

const MAX_ENTRIES_PER_SCENE = 200;

type MemoryRow = {
  entry_id: string;
  scene_id: string;
  role: string;
  message_type: string;
  content: string;
  metadata_json: string;
  timestamp: number;
};

/**
 * 鎻掍欢鐭湡璁板繂浠撳簱銆?
 * 鎸?extension_id + scene_id 闅旂锛岃嚜鍔ㄦ窐姹拌秴闄愭棫璁板綍銆?
 */
export class ExtensionShortTermMemoryRepository implements IExtensionShortTermMemory {
  constructor(private readonly extensionId: string) {}

  async append(input: ExtensionMemoryEntryInput): Promise<ExtensionMemoryEntry> {
    const entry: ExtensionMemoryEntry = {
      entry_id: randomUUID(),
      scene_id: input.scene_id,
      role: input.role,
      message_type: input.message_type,
      content: input.content,
      metadata: input.metadata,
      timestamp: Date.now(),
    };

    DBManager.instance.db
      .prepare(
        `INSERT INTO extension_short_term_memory
          (entry_id, extension_id, scene_id, role, message_type, content, metadata_json, timestamp)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?)`
      )
      .run(
        entry.entry_id,
        this.extensionId,
        entry.scene_id,
        entry.role,
        entry.message_type,
        entry.content,
        JSON.stringify(entry.metadata),
        entry.timestamp,
      );

    this.evictOldEntries(entry.scene_id);
    return entry;
  }

  async getRecent(sceneId: string, limit: number = 50): Promise<ExtensionMemoryEntry[]> {
    const rows = DBManager.instance.db
      .prepare(
        `SELECT entry_id, scene_id, role, message_type, content, metadata_json, timestamp
         FROM extension_short_term_memory
         WHERE extension_id = ? AND scene_id = ?
         ORDER BY timestamp DESC
         LIMIT ?`
      )
      .all(this.extensionId, sceneId, limit) as MemoryRow[];

    return rows.reverse().map(this.rowToEntry);
  }

  async getByType(sceneId: string, messageType: string, limit: number = 50): Promise<ExtensionMemoryEntry[]> {
    const rows = DBManager.instance.db
      .prepare(
        `SELECT entry_id, scene_id, role, message_type, content, metadata_json, timestamp
         FROM extension_short_term_memory
         WHERE extension_id = ? AND scene_id = ? AND message_type = ?
         ORDER BY timestamp DESC
         LIMIT ?`
      )
      .all(this.extensionId, sceneId, messageType, limit) as MemoryRow[];

    return rows.reverse().map(this.rowToEntry);
  }

  async clearScene(sceneId: string): Promise<void> {
    DBManager.instance.db
      .prepare('DELETE FROM extension_short_term_memory WHERE extension_id = ? AND scene_id = ?')
      .run(this.extensionId, sceneId);
  }

  private evictOldEntries(sceneId: string): void {
    DBManager.instance.db
      .prepare(
        `DELETE FROM extension_short_term_memory
         WHERE extension_id = ? AND scene_id = ? AND entry_id NOT IN (
           SELECT entry_id FROM extension_short_term_memory
           WHERE extension_id = ? AND scene_id = ?
           ORDER BY timestamp DESC
           LIMIT ?
         )`
      )
      .run(this.extensionId, sceneId, this.extensionId, sceneId, MAX_ENTRIES_PER_SCENE);
  }

  private rowToEntry(row: MemoryRow): ExtensionMemoryEntry {
    let metadata: Record<string, unknown> = {};
    try {
      metadata = JSON.parse(row.metadata_json);
    } catch { /* ignore */ }

    return {
      entry_id: row.entry_id,
      scene_id: row.scene_id,
      role: row.role as ExtensionMemoryEntry["role"],
      message_type: row.message_type,
      content: row.content,
      metadata,
      timestamp: row.timestamp,
    };
  }
}

