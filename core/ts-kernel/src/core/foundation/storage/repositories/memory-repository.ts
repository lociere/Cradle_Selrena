/**
 * 记忆数据访问层
 * 负责长期记忆的CRUD操作，是记忆持久化的唯一入口
 */
import { randomUUID } from "crypto";
import { DBManager } from "../db-manager";
import { getLogger } from "../../logger/logger";
import {
  LongTermMemoryFragment,
  LongTermMemoryType,
  CoreException,
  ErrorCode,
} from "@cradle-selrena/protocol";

const logger = getLogger("memory-repository");

export interface ShortTermMemoryFragmentRecord {
  memory_id: string;
  scene_id: string;
  role: string;
  content: string;
  importance: number;
  timestamp: string;
  trace_id?: string;
}

export interface ShortTermSceneSnapshot {
  scene_id: string;
  total_records: number;
  latest_timestamp: string | null;
  recent_records: ShortTermMemoryFragmentRecord[];
}

/**
 * 记忆数据访问层
 * 单例模式
 */
export class MemoryRepository {
  private static _instance: MemoryRepository | null = null;

  public static get instance(): MemoryRepository {
    if (!MemoryRepository._instance) {
      MemoryRepository._instance = new MemoryRepository();
    }
    return MemoryRepository._instance;
  }

  private constructor() {}

  public addMemory(memory: Omit<LongTermMemoryFragment, "memory_id" | "timestamp">): string {
    const db = DBManager.instance.getDB();
    const memoryId = randomUUID();
    const timestamp = new Date().toISOString();

    try {
      const stmt = db.prepare(`
        INSERT INTO long_term_memory (
          memory_id, content, memory_type, weight, tags, scene_id, timestamp
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
      `);

      stmt.run(
        memoryId,
        memory.content,
        memory.memory_type,
        memory.weight,
        JSON.stringify(memory.tags || []),
        memory.scene_id || "",
        timestamp
      );

      logger.debug("记忆新增成功", { memory_id: memoryId, memory_type: memory.memory_type });
      return memoryId;
    } catch (error) {
      logger.error("记忆新增失败", { error: (error as Error).message });
      throw new CoreException(
        `记忆新增失败: ${(error as Error).message}`,
        ErrorCode.PERSISTENCE_ERROR
      );
    }
  }

  public batchAddMemories(memories: Array<Omit<LongTermMemoryFragment, "memory_id" | "timestamp">>): string[] {
    return DBManager.instance.transaction((db) => {
      const memoryIds: string[] = [];
      const stmt = db.prepare(`
        INSERT INTO long_term_memory (
          memory_id, content, memory_type, weight, tags, scene_id, timestamp
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
      `);

      for (const memory of memories) {
        const memoryId = randomUUID();
        const timestamp = new Date().toISOString();
        stmt.run(
          memoryId,
          memory.content,
          memory.memory_type,
          memory.weight,
          JSON.stringify(memory.tags || []),
          memory.scene_id || "",
          timestamp
        );
        memoryIds.push(memoryId);
      }

      logger.debug("批量新增记忆完成", { count: memoryIds.length });
      return memoryIds;
    });
  }

  public getRelevantMemories(query: string, limit: number = 5, memoryType?: LongTermMemoryType): LongTermMemoryFragment[] {
    const db = DBManager.instance.getDB();
    const keywords = query.toLowerCase().split(/\s+/).filter((k) => k.length > 0);

    try {
      let sql = `SELECT * FROM long_term_memory WHERE 1=1`;
      const params: unknown[] = [];

      if (memoryType) {
        sql += ` AND memory_type = ?`;
        params.push(memoryType);
      }

      if (keywords.length > 0) {
        const keywordConditions = keywords.map(() => `LOWER(content) LIKE ?`).join(" OR ");
        sql += ` AND (${keywordConditions})`;
        keywords.forEach((kw) => params.push(`%${kw}%`));
      }

      sql += ` ORDER BY weight DESC, timestamp DESC LIMIT ?`;
      params.push(limit);

      const stmt = db.prepare(sql);
      const rows = stmt.all(...params) as any[];

      return rows.map((row) => ({
        memory_id: row.memory_id,
        content: row.content,
        memory_type: row.memory_type as LongTermMemoryType,
        weight: row.weight,
        tags: JSON.parse(row.tags),
        scene_id: row.scene_id,
        timestamp: row.timestamp,
      }));
    } catch (error) {
      logger.error("记忆检索失败", { query: query, error: (error as Error).message });
      throw new CoreException(`记忆检索失败: ${(error as Error).message}`, ErrorCode.PERSISTENCE_ERROR);
    }
  }

  public getAllMemories(): LongTermMemoryFragment[] {
    const db = DBManager.instance.getDB();

    try {
      const rows = db.prepare(`SELECT * FROM long_term_memory ORDER BY timestamp DESC`).all() as any[];
      return rows.map((row) => ({
        memory_id: row.memory_id,
        content: row.content,
        memory_type: row.memory_type as LongTermMemoryType,
        weight: row.weight,
        tags: JSON.parse(row.tags),
        scene_id: row.scene_id,
        timestamp: row.timestamp,
      }));
    } catch (error) {
      logger.error("全量记忆获取失败", { error: (error as Error).message });
      throw new CoreException(`全量记忆获取失败: ${(error as Error).message}`, ErrorCode.PERSISTENCE_ERROR);
    }
  }

  public updateMemoryWeight(memoryId: string, newWeight: number): void {
    const db = DBManager.instance.getDB();

    try {
      const stmt = db.prepare(`
        UPDATE long_term_memory
        SET weight = ?, updated_at = CURRENT_TIMESTAMP
        WHERE memory_id = ?
      `);
      const result = stmt.run(newWeight, memoryId);

      if (result.changes === 0) {
        throw new CoreException(`记忆不存在: ${memoryId}`, ErrorCode.MEMORY_NOT_FOUND);
      }

      logger.debug("记忆权重更新成功", { memory_id: memoryId, new_weight: newWeight });
    } catch (error) {
      logger.error("记忆权重更新失败", { memory_id: memoryId, error: (error as Error).message });
      throw error;
    }
  }

  public deleteMemory(memoryId: string): void {
    const db = DBManager.instance.getDB();

    try {
      const stmt = db.prepare(`DELETE FROM long_term_memory WHERE memory_id = ?`);
      const result = stmt.run(memoryId);

      if (result.changes === 0) {
        throw new CoreException(`记忆不存在: ${memoryId}`, ErrorCode.MEMORY_NOT_FOUND);
      }

      logger.info("记忆删除成功", { memory_id: memoryId });
    } catch (error) {
      logger.error("记忆删除失败", { memory_id: memoryId, error: (error as Error).message });
      throw error;
    }
  }

  public decayAllMemories(decayRate: number = 0.02): void {
    const db = DBManager.instance.getDB();

    try {
      const stmt = db.prepare(`
        UPDATE long_term_memory
        SET weight = MAX(0.1, weight - ?), updated_at = CURRENT_TIMESTAMP
        WHERE memory_type != ?
      `);
      const result = stmt.run(decayRate, LongTermMemoryType.PREFERENCE);

      logger.debug("全量记忆权重衰减完成", { affected_rows: result.changes, decay_rate: decayRate });
    } catch (error) {
      logger.error("全量记忆权重衰减失败", { error: (error as Error).message });
      throw new CoreException(`记忆衰减失败: ${(error as Error).message}`, ErrorCode.PERSISTENCE_ERROR);
    }
  }

  public upsertMemoryFromSync(memory: LongTermMemoryFragment): void {
    const db = DBManager.instance.getDB();
    try {
      const stmt = db.prepare(`
        INSERT INTO long_term_memory (
          memory_id, content, memory_type, weight, tags, scene_id, timestamp
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(memory_id) DO UPDATE SET
          content=excluded.content,
          memory_type=excluded.memory_type,
          weight=excluded.weight,
          tags=excluded.tags,
          scene_id=excluded.scene_id,
          timestamp=excluded.timestamp,
          updated_at=CURRENT_TIMESTAMP
      `);

      stmt.run(
        memory.memory_id,
        memory.content,
        memory.memory_type,
        memory.weight,
        JSON.stringify(memory.tags || []),
        memory.scene_id || "",
        memory.timestamp
      );

      logger.debug("长期记忆同步写入完成", { memory_id: memory.memory_id });
    } catch (error) {
      logger.error("长期记忆同步写入失败", { error: (error as Error).message });
      throw new CoreException(`长期记忆同步写入失败: ${(error as Error).message}`, ErrorCode.PERSISTENCE_ERROR);
    }
  }

  public upsertShortTermMemoryFromSync(fragment: ShortTermMemoryFragmentRecord): void {
    const db = DBManager.instance.getDB();
    try {
      const stmt = db.prepare(`
        INSERT INTO short_term_memory (
          memory_id, scene_id, role, content, importance, trace_id, timestamp
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(memory_id) DO UPDATE SET
          scene_id=excluded.scene_id,
          role=excluded.role,
          content=excluded.content,
          importance=excluded.importance,
          trace_id=excluded.trace_id,
          timestamp=excluded.timestamp
      `);

      stmt.run(
        fragment.memory_id,
        fragment.scene_id,
        fragment.role,
        fragment.content,
        fragment.importance,
        fragment.trace_id || "",
        fragment.timestamp
      );

      logger.debug("短期记忆同步写入完成", {
        memory_id: fragment.memory_id,
        scene_id: fragment.scene_id,
      });
    } catch (error) {
      logger.error("短期记忆同步写入失败", { error: (error as Error).message });
      throw new CoreException(`短期记忆同步写入失败: ${(error as Error).message}`, ErrorCode.PERSISTENCE_ERROR);
    }
  }

  public getShortTermSceneSnapshot(sceneId: string, recentLimit: number = 50): ShortTermSceneSnapshot {
    const db = DBManager.instance.getDB();
    try {
      const countRow = db.prepare(
        `SELECT COUNT(1) AS total_records, MAX(timestamp) AS latest_timestamp FROM short_term_memory WHERE scene_id = ?`
      ).get(sceneId) as { total_records: number; latest_timestamp: string | null };

      const rows = db.prepare(
        `SELECT memory_id, scene_id, role, content, importance, trace_id, timestamp
         FROM short_term_memory
         WHERE scene_id = ?
         ORDER BY timestamp DESC
         LIMIT ?`
      ).all(sceneId, recentLimit) as Array<{
        memory_id: string;
        scene_id: string;
        role: string;
        content: string;
        importance: number;
        trace_id: string;
        timestamp: string;
      }>;

      const recentRecords = rows.reverse().map((row) => ({
        memory_id: row.memory_id,
        scene_id: row.scene_id,
        role: row.role,
        content: row.content,
        importance: row.importance,
        trace_id: row.trace_id || undefined,
        timestamp: row.timestamp,
      }));

      return {
        scene_id: sceneId,
        total_records: Number(countRow?.total_records || 0),
        latest_timestamp: countRow?.latest_timestamp || null,
        recent_records: recentRecords,
      };
    } catch (error) {
      logger.error("获取短期记忆场景快照失败", {
        scene_id: sceneId,
        error: (error as Error).message,
      });
      throw new CoreException(`获取短期记忆场景快照失败: ${(error as Error).message}`, ErrorCode.PERSISTENCE_ERROR);
    }
  }
}
