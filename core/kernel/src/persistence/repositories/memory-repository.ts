/**
 * 记忆数据访问层
 * 负责长期记忆的CRUD操作，是记忆持久化的唯一入口
 */
import { randomUUID } from "crypto";
import { DBManager } from "../db-manager";
import { getLogger } from "../../observability/logger";
import {
  LongTermMemoryFragment,
  LongTermMemoryType,
  CoreException,
  ErrorCode,
} from "@cradle-selrena/protocol";

const logger = getLogger("memory-repository");

/**
 * 记忆数据访问层
 * 单例模式
 */
export class MemoryRepository {
  private static _instance: MemoryRepository | null = null;

  /**
   * 获取单例实例
   */
  public static get instance(): MemoryRepository {
    if (!MemoryRepository._instance) {
      MemoryRepository._instance = new MemoryRepository();
    }
    return MemoryRepository._instance;
  }

  private constructor() {}

  /**
   * 新增记忆
   * @param memory 记忆片段（不含memory_id和timestamp）
   * @returns 新增的记忆ID
   */
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

  /**
   * 批量新增记忆
   * @param memories 记忆片段列表
   * @returns 新增的记忆ID列表
   */
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

  /**
   * 获取相关记忆（关键词匹配）
   */
  public getRelevantMemories(query: string, limit: number = 5, memoryType?: LongTermMemoryType): LongTermMemoryFragment[] {
    const db = DBManager.instance.getDB();
    const keywords = query.toLowerCase().split(/\s+/).filter((k) => k.length > 0);

    try {
      let sql = `
        SELECT * FROM long_term_memory
        WHERE 1=1
      `;
      const params: any[] = [];

      // 记忆类型过滤
      if (memoryType) {
        sql += ` AND memory_type = ?`;
        params.push(memoryType);
      }

      // 关键词匹配
      if (keywords.length > 0) {
        const keywordConditions = keywords.map(() => `LOWER(content) LIKE ?`).join(" OR ");
        sql += ` AND (${keywordConditions})`;
        keywords.forEach((kw) => params.push(`%${kw}%`));
      }

      // 按权重倒序，限制数量
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

  /**
   * 获取所有记忆
   */
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

  /**
   * 更新记忆权重
   */
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

  /**
   * 删除记忆
   */
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

  /**
   * 全量记忆权重衰减
   */
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
}
