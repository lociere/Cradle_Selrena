import fs from "fs-extra";
import path from "path";
import {
  MemorySyncEvent,
  ShortTermMemorySyncEvent,
  LongTermMemoryFragment,
} from "@cradle-selrena/protocol";
import { getLogger } from "../../core/observability/logger";
import { EventBus } from "../../core/event-bus/event-bus";
import {
  MemoryRepository,
  ShortTermMemoryFragmentRecord,
} from "../../infrastructure/persistence/repositories/memory-repository";
import { ConfigManager } from "../../core/config/config-manager";
import { resolveDataDir } from "../../core/utils/path-utils";

const logger = getLogger("memory-sync-manager");

export class MemorySyncManager {
  private static _instance: MemorySyncManager | null = null;
  private _initialized = false;
  private _shortTermDir = "";

  public static get instance(): MemorySyncManager {
    if (!MemorySyncManager._instance) {
      MemorySyncManager._instance = new MemorySyncManager();
    }
    return MemorySyncManager._instance;
  }

  private constructor() {}

  public async init(): Promise<void> {
    if (this._initialized) {
      return;
    }

    const cfg = ConfigManager.instance.getConfig();
    const dataDir = resolveDataDir(cfg.app?.data_dir);
    this._shortTermDir = path.join(dataDir, "memory", "short_term");
    await fs.ensureDir(this._shortTermDir);

    EventBus.instance.subscribe("MemorySyncEvent", this.handleLongTermMemorySync);
    EventBus.instance.subscribe("ShortTermMemorySyncEvent", this.handleShortTermMemorySync);

    this._initialized = true;
    logger.info("记忆同步管理器初始化完成", { short_term_dir: this._shortTermDir });
  }

  public async shutdown(): Promise<void> {
    if (!this._initialized) {
      return;
    }
    EventBus.instance.unsubscribe("MemorySyncEvent", this.handleLongTermMemorySync);
    EventBus.instance.unsubscribe("ShortTermMemorySyncEvent", this.handleShortTermMemorySync);
    this._initialized = false;
    logger.info("记忆同步管理器已停止");
  }

  private handleLongTermMemorySync = async (event: MemorySyncEvent): Promise<void> => {
    const memory = event?.payload?.memory as LongTermMemoryFragment | undefined;
    if (!memory || !memory.memory_id) {
      logger.warn("收到无效长期记忆同步事件，已忽略");
      return;
    }
    MemoryRepository.instance.upsertMemoryFromSync(memory);
  };

  private handleShortTermMemorySync = async (event: ShortTermMemorySyncEvent): Promise<void> => {
    const fragment = event?.payload?.fragment as ShortTermMemoryFragmentRecord | undefined;
    if (!fragment || !fragment.memory_id || !fragment.scene_id) {
      logger.warn("收到无效短期记忆同步事件，已忽略");
      return;
    }

    MemoryRepository.instance.upsertShortTermMemoryFromSync(fragment);
    await this.appendShortTermFile(fragment);
  };

  private async appendShortTermFile(fragment: ShortTermMemoryFragmentRecord): Promise<void> {
    const safeSceneId = this.sanitizeSceneId(fragment.scene_id);
    const filePath = path.join(this._shortTermDir, `${safeSceneId}.jsonl`);
    await fs.ensureFile(filePath);
    await fs.appendFile(filePath, `${JSON.stringify(fragment)}\n`, "utf-8");
  }

  private sanitizeSceneId(sceneId: string): string {
    return sceneId.replace(/[^a-zA-Z0-9._-]/g, "_");
  }
}
