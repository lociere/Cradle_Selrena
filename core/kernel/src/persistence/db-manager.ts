/**
 * DBManager - SQLite 管理器
 * 负责数据库连接、表创建与简单迁移
 */
import Database from 'better-sqlite3';
import path from 'path';
import fs from 'fs-extra';
import { getLogger } from '../observability/logger';
import { ConfigManager } from '../config/config-manager';

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

  public init(): void {
    if (this._isInitialized) return;
    const cfg = ConfigManager.instance.getConfig();
    const dataDir = cfg.app?.data_dir || path.resolve(process.cwd(), 'data');
    fs.ensureDirSync(dataDir);
    this._dbPath = path.join(dataDir, 'selrena.db');
    logger.info('打开数据库', { path: this._dbPath });
    this._db = new Database(this._dbPath);

    // 简单的表初始化示例
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

  public close(): void {
    if (!this._db) return;
    this._db.close();
    this._db = null;
    this._isInitialized = false;
    logger.info('数据库已关闭');
  }
}
