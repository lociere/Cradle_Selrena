import fs from 'fs-extra';
import path from 'path';

/**
 * 解析仓库根目录。
 *
 * 依次向上查找以下标识文件：pnpm-workspace.yaml -> .git -> package.json。
 * 如果在当前路径以外找不到这些标识，将返回 process.cwd()。
 */
export function resolveRepoRoot(): string {
  let dir = process.cwd();
  let lastPackageJson: string | null = null;

  while (true) {
    if (fs.existsSync(path.join(dir, 'pnpm-workspace.yaml'))) {
      return dir;
    }
    if (fs.existsSync(path.join(dir, '.git'))) {
      return dir;
    }
    if (fs.existsSync(path.join(dir, 'package.json'))) {
      lastPackageJson = dir;
    }

    const parent = path.dirname(dir);
    if (parent === dir) break;
    dir = parent;
  }

  return lastPackageJson || process.cwd();
}

/**
 * 统一计算项目 `data` 目录的绝对路径。
 *
 * - 如果传入的是绝对路径，则直接返回
 * - 否则将相对路径视为相对于仓库根目录
 * - 如果未传入，则返回 <repoRoot>/data
 */
export function resolveDataDir(dataDir?: string): string {
  const repoRoot = resolveRepoRoot();
  if (!dataDir) {
    return path.join(repoRoot, 'data');
  }
  if (path.isAbsolute(dataDir)) {
    return dataDir;
  }
  return path.join(repoRoot, dataDir);
}

/**
 * 统一计算项目日志目录的绝对路径。
 *
 * - `dataDir` 缺省时使用 <repoRoot>/data
 * - `logDir` 缺省时使用 dataDir 下的 logs
 * - `logDir` 为绝对路径时直接返回
 * - `logDir` 为相对路径时拼接到 dataDir 下
 */
export function resolveLogDir(dataDir?: string, logDir?: string): string {
  if (logDir && path.isAbsolute(logDir)) {
    return logDir;
  }
  const baseData = resolveDataDir(dataDir);
  if (!logDir) {
    return path.join(baseData, 'logs');
  }
  return path.join(baseData, logDir);
}
