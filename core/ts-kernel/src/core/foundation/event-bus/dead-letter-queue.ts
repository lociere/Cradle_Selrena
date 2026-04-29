/**
 * DeadLetterQueue — TS 端死信队列
 *
 * v4.5 Schema-First: 事件处理器失败时持久化到本地 SQLite。
 * 与 Python 端 dlq_manager.py 对称设计。
 *
 * 职责：
 *   1. 接收 EventBus 中 handler 执行失败的事件与异常
 *   2. 持久化到内核共享的 selrena.db
 *   3. 提供查询接口供审计/重放
 */
import { getLogger } from '../logger/logger';
import { DBManager } from '../storage/db-manager';

const logger = getLogger('dlq');

export interface DeadLetterRecord {
  id: number;
  trace_id: string;
  event_type: string;
  payload: string;
  error_message: string;
  stack_trace: string;
  created_at: string;
  replayed: boolean;
}

/**
 * TS 端死信队列管理器（单例）
 *
 * 使用内核共享的 better-sqlite3 实例（通过 DBManager）做同步写入。
 * TS 内核事件总线是 async 但单线程，同步写入不会阻塞其他线程。
 */
export class DeadLetterQueue {
  private static _instance: DeadLetterQueue | null = null;
  private _initialized = false;

  public static get instance(): DeadLetterQueue {
    if (!DeadLetterQueue._instance) {
      DeadLetterQueue._instance = new DeadLetterQueue();
    }
    return DeadLetterQueue._instance;
  }

  private constructor() {}

  /**
   * 初始化 DLQ 表结构。
   * 在 DBManager 初始化之后由 app.ts 调用。
   */
  public init(): void {
    if (this._initialized) return;
    try {
      const db = DBManager.instance.getDB();
      db.exec(`
        CREATE TABLE IF NOT EXISTS dead_letters_ts (
          id          INTEGER PRIMARY KEY AUTOINCREMENT,
          trace_id    TEXT NOT NULL,
          event_type  TEXT NOT NULL,
          payload     TEXT NOT NULL DEFAULT '{}',
          error_message TEXT NOT NULL,
          stack_trace TEXT DEFAULT '',
          created_at  TEXT NOT NULL,
          replayed    INTEGER DEFAULT 0
        )
      `);
      db.exec(
        `CREATE INDEX IF NOT EXISTS idx_dlts_trace ON dead_letters_ts(trace_id)`
      );
      this._initialized = true;
      logger.info('TS 端死信队列表已就绪');
    } catch (error) {
      logger.error('DLQ 初始化失败', { error: (error as Error).message });
    }
  }

  /**
   * 将失败的事件写入死信队列。
   */
  public enqueue(
    traceId: string,
    eventType: string,
    payload: unknown,
    error: Error,
  ): void {
    if (!this._initialized) {
      logger.warn('DLQ 未初始化，丢弃死信', { event_type: eventType, trace_id: traceId });
      return;
    }

    let payloadJson: string;
    try {
      payloadJson = JSON.stringify(payload, null, 0);
    } catch {
      payloadJson = String(payload);
    }

    try {
      const db = DBManager.instance.getDB();
      db.prepare(`
        INSERT INTO dead_letters_ts (trace_id, event_type, payload, error_message, stack_trace, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
      `).run(
        traceId,
        eventType,
        payloadJson,
        error.message,
        error.stack ?? '',
        new Date().toISOString(),
      );
      logger.warn('事件已写入 TS 死信队列', {
        trace_id: traceId,
        event_type: eventType,
        error: error.message,
      });
    } catch (dbError) {
      // DLQ 自身故障不应影响事件总线
      logger.error('DLQ 写入失败', { error: (dbError as Error).message });
    }
  }

  /**
   * 查询最近的死信记录。
   */
  public queryRecent(limit: number = 50): DeadLetterRecord[] {
    if (!this._initialized) return [];
    try {
      const db = DBManager.instance.getDB();
      const rows = db.prepare(
        `SELECT id, trace_id, event_type, payload, error_message, stack_trace, created_at, replayed
         FROM dead_letters_ts WHERE replayed = 0 ORDER BY created_at DESC LIMIT ?`
      ).all(limit) as DeadLetterRecord[];
      return rows;
    } catch {
      return [];
    }
  }

  /**
   * 按 trace_id 查询死信记录。
   */
  public queryByTrace(traceId: string): DeadLetterRecord[] {
    if (!this._initialized) return [];
    try {
      const db = DBManager.instance.getDB();
      return db.prepare(
        `SELECT id, trace_id, event_type, payload, error_message, stack_trace, created_at, replayed
         FROM dead_letters_ts WHERE trace_id = ? ORDER BY created_at DESC`
      ).all(traceId) as DeadLetterRecord[];
    } catch {
      return [];
    }
  }

  /**
   * 标记死信为已重放。
   */
  public markReplayed(recordId: number): void {
    if (!this._initialized) return;
    try {
      const db = DBManager.instance.getDB();
      db.prepare('UPDATE dead_letters_ts SET replayed = 1 WHERE id = ?').run(recordId);
    } catch (error) {
      logger.error('标记重放失败', { record_id: recordId, error: (error as Error).message });
    }
  }
}
