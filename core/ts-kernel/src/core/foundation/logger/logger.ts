/**
 * 可观测性 Logger（TS 内核全局日志器）
 * ─────────────────────────────────────────────────────────────
 * • 基于 winston，输出到控制台 + 主日志文件 + 错误专属日志文件
 * • 控制台  彩色 + 模块标签格式：`HH:mm:ss.SSS [level] [module] 消息 {meta}`
 * • 文件     JSON 格式，便于后续离线分析
 * • 轮转    主日志 10 MB × 5；错误日志 5 MB × 3
 * • 幂等性  initLogger 重复调用安全
 */
import { createLogger, format, transports, Logger } from 'winston';
import path from 'path';
import fs from 'fs-extra';
import { resolveRepoRoot, resolveLogDir } from '../utils/path-utils';

const { combine, timestamp, printf, json, colorize } = format;

// ──────────────────────────────────────────────────────────────────────────────
// 内部状态
// ──────────────────────────────────────────────────────────────────────────────

let _initialized = false;

// ──────────────────────────────────────────────────────────────────────────────
// 日志目录（优先 LOG_DIR 环境变量）
// ──────────────────────────────────────────────────────────────────────────────

function _resolveInitialLogDir(): string {
  if (process.env.LOG_DIR) return path.resolve(process.env.LOG_DIR);
  return path.join(resolveRepoRoot(), 'data', 'logs');
}

const _initialLogDir = _resolveInitialLogDir();
fs.ensureDirSync(_initialLogDir);

// ──────────────────────────────────────────────────────────────────────────────
// 格式定义
// ──────────────────────────────────────────────────────────────────────────────

/**
 * 控制台格式：`HH:mm:ss.SSS [level] [module] 消息 {meta}`
 *   - level   由 colorize() 预先着色
 *   - module  Cyan 高亮标签
 *   - meta    灰色 JSON（仅当存在时才输出）
 */
const _consoleFormat = printf(({ level, message, timestamp: ts, module: mod, ...meta }) => {
  const modTag = mod ? ` \x1b[36m[${mod}]\x1b[0m` : '';
  // 过滤掉 winston 内部字段，避免污染 meta 显示
  const { splat: _s, ...cleanMeta } = meta as any;
  const metaStr = Object.keys(cleanMeta).length
    ? ` \x1b[90m${JSON.stringify(cleanMeta)}\x1b[0m`
    : '';
  return `${ts} [${level}]${modTag} ${message}${metaStr}`;
});

// ──────────────────────────────────────────────────────────────────────────────
// 核心 logger 实例
// ──────────────────────────────────────────────────────────────────────────────

const _baseLogger: Logger = createLogger({
  level: process.env.LOG_LEVEL ?? 'info',
  // 文件 transport 使用带时间戳的 JSON 格式
  format: combine(timestamp(), json()),
  transports: [
    // ── 控制台
    new transports.Console({
      format: combine(
        colorize({ level: true }),  // 仅为 level 字段着色
        timestamp({ format: 'HH:mm:ss.SSS' }),
        _consoleFormat,
      ),
    }),
    // ── 主日志文件（全量，10 MB × 5 轮转）
    new transports.File({
      filename: path.join(_initialLogDir, 'runtime.log'),
      level: 'debug',
      maxsize: 10 * 1024 * 1024,
      maxFiles: 5,
    } as any),
    // ── 错误日志文件（WARNING 以上，5 MB × 3 轮转，快速排查首选）
    new transports.File({
      filename: path.join(_initialLogDir, 'runtime-error.log'),
      level: 'warn',
      maxsize: 5 * 1024 * 1024,
      maxFiles: 3,
    } as any),
  ],
});

// ──────────────────────────────────────────────────────────────────────────────
// 公共接口类型
// ──────────────────────────────────────────────────────────────────────────────

/** 模块级日志器接口 */
export interface ILogger {
  debug(message: string, meta?: Record<string, unknown>): void;
  info(message: string, meta?: Record<string, unknown>): void;
  warn(message: string, meta?: Record<string, unknown>): void;
  error(message: string, meta?: Record<string, unknown>): void;
  /**
   * 严重错误。与 error 相同级别，但在 meta 中附加 `critical: true` 标记，
   * 便于日志收集系统单独告警。
   */
  critical(message: string, meta?: Record<string, unknown>): void;
  /**
   * 动态级别输出（由调用方传入 winston 级别字符串，如 `"info"`、`"warn"`）。
   * 用于外部系统（如 Python AI 层）通过 IPC 上报指定级别的日志。
   */
  log(level: string, message: string, meta?: Record<string, unknown>): void;
}

// ──────────────────────────────────────────────────────────────────────────────
// 公共 API
// ──────────────────────────────────────────────────────────────────────────────

/**
 * 全局日志器初始化（由 app.ts 在加载配置后调用，幂等安全）。
 * 主要作用：将日志级别与文件输出路径更新为配置指定值。
 */
export function initLogger(config: {
  log_level?: string;
  data_dir?: string;
  log_dir?: string;
} = {}): void {
  if (_initialized) return;
  _initialized = true;

  const level = config.log_level ?? process.env.LOG_LEVEL ?? 'info';
  _baseLogger.level = level;

  const targetDir = process.env.LOG_DIR
    ? path.resolve(process.env.LOG_DIR)
    : resolveLogDir(config.data_dir, config.log_dir);

  // 仅当目录与初始目录不同时才替换文件 transport，避免无谓的文件操作
  if (path.resolve(targetDir) !== path.resolve(_initialLogDir)) {
    fs.ensureDirSync(targetDir);
    _baseLogger.transports
      .filter((t) => t instanceof transports.File)
      .forEach((t) => _baseLogger.remove(t));
    _baseLogger.add(new transports.File({
      filename: path.join(targetDir, 'runtime.log'),
      level: 'debug',
      maxsize: 10 * 1024 * 1024,
      maxFiles: 5,
    } as any));
    _baseLogger.add(new transports.File({
      filename: path.join(targetDir, 'runtime-error.log'),
      level: 'warn',
      maxsize: 5 * 1024 * 1024,
      maxFiles: 3,
    } as any));
  }
}

/** 关闭所有 transport（进程退出前调用）。 */
export function closeLogger(): void {
  _baseLogger.transports.forEach((t) => t.close?.());
}

/**
 * 获取模块级 logger。
 * 每条日志会自动注入 `module` 字段，无需在每次调用时手动传入。
 *
 * @param name 模块名（如 `"config-manager"`、`"ipc-server"`）
 */
export function getLogger(name = 'core'): ILogger {
  return {
    debug:    (message, meta = {}) => _baseLogger.debug(message,   { module: name, ...meta }),
    info:     (message, meta = {}) => _baseLogger.info(message,    { module: name, ...meta }),
    warn:     (message, meta = {}) => _baseLogger.warn(message,    { module: name, ...meta }),
    error:    (message, meta = {}) => _baseLogger.error(message,   { module: name, ...meta }),
    critical: (message, meta = {}) => _baseLogger.error(message,   { module: name, critical: true, ...meta }),
    log:      (level, message, meta = {}) => _baseLogger.log(level, message, { module: name, ...meta }),
  };
}

export { _baseLogger as baseLogger };
