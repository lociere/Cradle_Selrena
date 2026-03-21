/**
 * DBManager - SQLite 管理器
 * 负责数据库连接、表创建与简单迁移
 */
import Database from 'better-sqlite3';
import path from 'path';
import fs from 'fs-extra';
import { getLogger } from '../logger/logger';
import { ConfigManager } from '../config/config-manager';
import { resolveDataDir } from '../utils/path-utils';

const logger = getLogger('db-manager');

export class DBManager {
  private static _instance: DBManager | null = null;
  private _db: Database.Database | null = null;
  private _dbPath = '';
  private _isInitialized = false;

  public static get instance(): DBManager {
    if (!DBManager._instance) DBManager._instance = new DBManager();
    return DBManager._instance;
  }

  private constructor() {}

  public async init(): Promise<void> {
    if (this._isInitialized) return;
    const cfg = ConfigManager.instance.getConfig();
    const dataDir = resolveDataDir(cfg.app?.data_dir);
    fs.ensureDirSync(dataDir);
    this._dbPath = path.join(dataDir, 'selrena.db');
    logger.info('打开数据库', { path: this._dbPath });
    this._db = new Database(this._dbPath);

    // 记忆表（供 MemoryRepository 使用）
    this._db.prepare(`CREATE TABLE IF NOT EXISTS long_term_memory (
      memory_id   TEXT PRIMARY KEY,
      content     TEXT NOT NULL,
      memory_type TEXT NOT NULL DEFAULT 'episodic',
      weight      REAL NOT NULL DEFAULT 1.0,
      tags        TEXT NOT NULL DEFAULT '[]',
      scene_id    TEXT NOT NULL DEFAULT '',
      timestamp   TEXT NOT NULL
    )`).run();

    this._db.prepare(`CREATE TABLE IF NOT EXISTS short_term_memory (
      memory_id   TEXT PRIMARY KEY,
      scene_id    TEXT NOT NULL,
      role        TEXT NOT NULL,
      content     TEXT NOT NULL,
      importance  REAL NOT NULL DEFAULT 0.5,
      trace_id    TEXT NOT NULL DEFAULT '',
      timestamp   TEXT NOT NULL
    )`).run();

    this._db.prepare(`CREATE INDEX IF NOT EXISTS idx_short_term_memory_scene_time
      ON short_term_memory(scene_id, timestamp)
    `).run();

    // 旧 memories 表保留向下兼容（已弃用，新代码请使用 long_term_memory）
    this._db.prepare(`CREATE TABLE IF NOT EXISTS memories (
      id TEXT PRIMARY KEY,
      content TEXT NOT NULL,
      created_at INTEGER NOT NULL,
      meta TEXT
    )`).run();

    this._isInitialized = true;
    logger.info('数据库初始化完成');
  }

  public get db(): Database.Database {
    if (!this._db) throw new Error('数据库未初始化');
    return this._db;
  }

  public getDB(): Database.Database {
    return this.db;
  }

  public transaction<T>(fn: (db: Database.Database) => T): T {
    const db = this.db;
    const tx = db.transaction(fn as any);
    return tx();
  }

  public async close(): Promise<void> {
    if (!this._db) return;
    this._db.close();
    this._db = null;
    this._isInitialized = false;
    logger.info('数据库已关闭');
  }
}
