import Database from 'better-sqlite3';
import fs from 'fs-extra';
import path from 'path';
import { ConfigManager } from '../config/config-manager';
import { getLogger } from '../logger/logger';
import { resolveDataDir } from '../utils/path-utils';

const logger = getLogger('db-manager');

export class DBManager {
  private static _instance: DBManager | null = null;
  private _db: Database.Database | null = null;
  private _dbPath = '';
  private _isInitialized = false;

  public static get instance(): DBManager {
    if (!DBManager._instance) {
      DBManager._instance = new DBManager();
    }
    return DBManager._instance;
  }

  private constructor() {}

  public async init(): Promise<void> {
    if (this._isInitialized) {
      return;
    }

    const config = ConfigManager.instance.getConfig();
    const dataDir = resolveDataDir(config.system?.data_dir);
    fs.ensureDirSync(dataDir);

    this._dbPath = path.join(dataDir, 'selrena.db');
    logger.info('打开数据库', { path: this._dbPath });

    this._db = new Database(this._dbPath);
    this.initializeCoreTables();
    this.initializeExtensionTables();
    this.ensureCoreSchemaCompatibility();
    this.migrateLegacyExtensionStorageTables();

    this._isInitialized = true;
    logger.info('数据库初始化完成');
  }

  public get db(): Database.Database {
    if (!this._db) {
      throw new Error('数据库未初始化');
    }
    return this._db;
  }

  public getDB(): Database.Database {
    return this.db;
  }

  public transaction<T>(fn: (db: Database.Database) => T): T {
    const database = this.db;
    const tx = database.transaction(() => fn(database));
    return tx();
  }

  public async close(): Promise<void> {
    if (!this._db) {
      return;
    }

    this._db.close();
    this._db = null;
    this._isInitialized = false;
    logger.info('数据库连接已关闭');
  }

  private initializeCoreTables(): void {
    this.db.prepare(`CREATE TABLE IF NOT EXISTS long_term_memory (
      memory_id   TEXT PRIMARY KEY,
      content     TEXT NOT NULL,
      memory_type TEXT NOT NULL DEFAULT 'episodic',
      weight      REAL NOT NULL DEFAULT 1.0,
      tags        TEXT NOT NULL DEFAULT '[]',
      scene_id    TEXT NOT NULL DEFAULT '',
      timestamp   TEXT NOT NULL,
      updated_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )`).run();

    this.db.prepare(`CREATE TABLE IF NOT EXISTS short_term_memory (
      memory_id   TEXT PRIMARY KEY,
      scene_id    TEXT NOT NULL,
      role        TEXT NOT NULL,
      content     TEXT NOT NULL,
      importance  REAL NOT NULL DEFAULT 0.5,
      trace_id    TEXT NOT NULL DEFAULT '',
      timestamp   TEXT NOT NULL
    )`).run();

    this.db.prepare(`CREATE INDEX IF NOT EXISTS idx_short_term_memory_scene_time
      ON short_term_memory(scene_id, timestamp)
    `).run();
  }

  private initializeExtensionTables(): void {
    this.db.prepare(`CREATE TABLE IF NOT EXISTS extension_storage (
      extension_id TEXT NOT NULL,
      key          TEXT NOT NULL,
      value_json   TEXT NOT NULL,
      updated_at   TEXT NOT NULL,
      PRIMARY KEY (extension_id, key)
    )`).run();

    this.db.prepare(`CREATE TABLE IF NOT EXISTS extension_short_term_memory (
      entry_id      TEXT PRIMARY KEY,
      extension_id  TEXT NOT NULL,
      scene_id      TEXT NOT NULL,
      role          TEXT NOT NULL,
      message_type  TEXT NOT NULL,
      content       TEXT NOT NULL,
      metadata_json TEXT NOT NULL DEFAULT '{}',
      timestamp     INTEGER NOT NULL
    )`).run();

    this.db.prepare(`CREATE INDEX IF NOT EXISTS idx_extension_stm_scene
      ON extension_short_term_memory(extension_id, scene_id, timestamp)
    `).run();

    this.db.prepare(`CREATE INDEX IF NOT EXISTS idx_extension_stm_type
      ON extension_short_term_memory(extension_id, scene_id, message_type, timestamp)
    `).run();
  }

  private ensureCoreSchemaCompatibility(): void {
    this.ensureColumnExists(
      'long_term_memory',
      'updated_at',
      'TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP',
    );
  }

  private migrateLegacyExtensionStorageTables(): void {
    if (this.hasTable('plugin_storage')) {
      try {
        this.db.prepare(`
          INSERT OR IGNORE INTO extension_storage (extension_id, key, value_json, updated_at)
          SELECT plugin_id, key, value_json, updated_at
          FROM plugin_storage
        `).run();
        logger.info('已迁移历史扩展存储数据', {
          from_table: 'plugin_storage',
          to_table: 'extension_storage',
        });
      } catch (error) {
        logger.warn('迁移历史扩展存储数据失败', {
          from_table: 'plugin_storage',
          error: error instanceof Error ? error.message : String(error),
        });
      }
    }

    if (this.hasTable('plugin_short_term_memory')) {
      try {
        this.db.prepare(`
          INSERT OR IGNORE INTO extension_short_term_memory (
            entry_id,
            extension_id,
            scene_id,
            role,
            message_type,
            content,
            metadata_json,
            timestamp
          )
          SELECT
            entry_id,
            plugin_id,
            scene_id,
            role,
            message_type,
            content,
            metadata_json,
            timestamp
          FROM plugin_short_term_memory
        `).run();
        logger.info('已迁移历史扩展短期记忆数据', {
          from_table: 'plugin_short_term_memory',
          to_table: 'extension_short_term_memory',
        });
      } catch (error) {
        logger.warn('迁移历史扩展短期记忆数据失败', {
          from_table: 'plugin_short_term_memory',
          error: error instanceof Error ? error.message : String(error),
        });
      }
    }
  }

  private ensureColumnExists(tableName: string, columnName: string, definition: string): void {
    const rows = this.db.prepare(`PRAGMA table_info(${tableName})`).all() as Array<{
      name?: string;
    }>;

    if (rows.some((row) => row.name === columnName)) {
      return;
    }

    this.db.prepare(`ALTER TABLE ${tableName} ADD COLUMN ${columnName} ${definition}`).run();
    logger.info('已补齐数据库列', { table_name: tableName, column_name: columnName });
  }

  private hasTable(tableName: string): boolean {
    const row = this.db.prepare(
      `SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?`,
    ).get(tableName) as { name?: string } | undefined;
    return row?.name === tableName;
  }
}