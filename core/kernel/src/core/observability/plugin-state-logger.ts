import { getLogger } from "./logger";

const logger = getLogger("plugin-state-logger");

function stableStringify(value: unknown): string {
  if (value === null || value === undefined) {
    return String(value);
  }
  if (typeof value !== "object") {
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) {
    return `[${value.map((item) => stableStringify(item)).join(",")}]`;
  }

  const entries = Object.entries(value as Record<string, unknown>)
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([key, nestedValue]) => `${JSON.stringify(key)}:${stableStringify(nestedValue)}`);
  return `{${entries.join(",")}}`;
}

export class PluginStateLogger {
  private static _instance: PluginStateLogger | null = null;

  public static get instance(): PluginStateLogger {
    if (!PluginStateLogger._instance) {
      PluginStateLogger._instance = new PluginStateLogger();
    }
    return PluginStateLogger._instance;
  }

  private readonly _snapshots = new Map<string, string>();

  private constructor() {}

  public logIfChanged(
    pluginId: string,
    level: "debug" | "info" | "warn" | "error" | "critical",
    stateKey: string,
    snapshot: unknown,
    message: string,
    meta: Record<string, unknown> = {}
  ): boolean {
    const compoundKey = `${pluginId}:${stateKey}`;
    const nextSnapshot = stableStringify(snapshot);
    const previousSnapshot = this._snapshots.get(compoundKey);
    if (previousSnapshot === nextSnapshot) {
      return false;
    }

    this._snapshots.set(compoundKey, nextSnapshot);

    const payload = {
      plugin_id: pluginId,
      state_key: stateKey,
      ...meta,
    };

    if (level === "debug") {
      logger.debug(message, payload);
      return true;
    }
    if (level === "warn") {
      logger.warn(message, payload);
      return true;
    }
    if (level === "error" || level === "critical") {
      logger.error(message, level === "critical" ? { critical: true, ...payload } : payload);
      return true;
    }

    logger.info(message, payload);
    return true;
  }
}
