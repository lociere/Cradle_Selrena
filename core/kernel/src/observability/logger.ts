/**
 * 可观测性 Logger
 * 使用 winston 输出结构化日志，支持 trace_id 透传
 */
import { createLogger, format, transports, Logger } from 'winston';
import path from 'path';
import fs from 'fs-extra';

const { combine, timestamp, printf, json } = format;

const logDir = path.resolve(process.cwd(), 'logs');
fs.ensureDirSync(logDir);

const defaultFormat = printf(({ level, message, timestamp: ts, ...meta }) => {
  const metaStr = Object.keys(meta).length ? ` ${JSON.stringify(meta)}` : '';
  return `${ts} [${level}] ${message}${metaStr}`;
});

const baseLogger: Logger = createLogger({
  level: process.env.LOG_LEVEL || 'info',
  format: combine(timestamp(), json()),
  transports: [
    new transports.File({ filename: path.join(logDir, 'app.log'), level: 'info' }),
    new transports.Console({ format: combine(timestamp(), defaultFormat) }),
  ],
});

/**
 * 获取模块级 logger
 * @param name 模块名
 */
export function initLogger(config: { log_level?: string } = {}) {
  const level = config.log_level || process.env.LOG_LEVEL || 'info';
  baseLogger.level = level;
}

export function closeLogger() {
  baseLogger.transports.forEach((t) => t.close?.());
}

export function getLogger(name = 'core') {
  return {
    info: (message: string, meta: Record<string, any> = {}) => baseLogger.info(message, { module: name, ...meta }),
    warn: (message: string, meta: Record<string, any> = {}) => baseLogger.warn(message, { module: name, ...meta }),
    error: (message: string, meta: Record<string, any> = {}) => baseLogger.error(message, { module: name, ...meta }),
    debug: (message: string, meta: Record<string, any> = {}) => baseLogger.debug(message, { module: name, ...meta }),
    critical: (message: string, meta: Record<string, any> = {}) => baseLogger.error(message, { module: name, ...meta }),
    log: (level: string, message: string, meta: Record<string, any> = {}) => baseLogger.log(level, message, { module: name, ...meta }),
  };
}

export { baseLogger };
