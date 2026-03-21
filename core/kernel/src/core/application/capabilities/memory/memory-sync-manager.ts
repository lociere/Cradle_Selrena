import fs from "fs-extra";
import path from "path";
import {
  MemorySyncEvent,
  ShortTermMemorySyncEvent,
  LongTermMemoryFragment,
} from "@cradle-selrena/protocol";
import { getLogger } from "../../../infrastructure/logger/logger";
import { EventBus } from "../../../infrastructure/event-bus/event-bus";
import {
  MemoryRepository,
  ShortTermMemoryFragmentRecord,
} from "../../../infrastructure/storage/repositories/memory-repository";
import { ConfigManager } from "../../../infrastructure/config/config-manager";
import { resolveDataDir } from "../../../infrastructure/utils/path-utils";

const logger = getLogger("memory-sync-manager");

export class MemorySyncManager {
  private static _instance: MemorySyncManager | null = null;
  private _initialized = false;
  private _shortTermDir = "";
  private _shortTermSnapshotDir = "";
  private readonly _snapshotEveryRecords = 20;
  private readonly _snapshotRecentLimit = 80;
  private readonly _sceneSyncCounters: Map<string, number> = new Map();

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
    this._shortTermSnapshotDir = path.join(this._shortTermDir, "snapshots");
    await fs.ensureDir(this._shortTermDir);
    await fs.ensureDir(this._shortTermSnapshotDir);

    EventBus.instance.subscribe("MemorySyncEvent", this.handleLongTermMemorySync);
    EventBus.instance.subscribe("ShortTermMemorySyncEvent", this.handleShortTermMemorySync);

    this._initialized = true;
    logger.info("记忆同步管理器初始化完成", {
      short_term_dir: this._shortTermDir,
      short_term_snapshot_dir: this._shortTermSnapshotDir,
      snapshot_every_records: this._snapshotEveryRecords,
    });
  }

  public async shutdown(): Promise<void> {
    if (!this._initialized) {
      return;
    }
    EventBus.instance.unsubscribe("MemorySyncEvent", this.handleLongTermMemorySync);
    EventBus.instance.unsubscribe("ShortTermMemorySyncEvent", this.handleShortTermMemorySync);
    this._sceneSyncCounters.clear();
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
    await this.maybeWriteShortTermSnapshot(fragment.scene_id);
  };

  private async appendShortTermFile(fragment: ShortTermMemoryFragmentRecord): Promise<void> {
    const safeSceneId = this.sanitizeSceneId(fragment.scene_id);
    const filePath = path.join(this._shortTermDir, `${safeSceneId}.jsonl`);
    await fs.ensureFile(filePath);
    await fs.appendFile(filePath, `${JSON.stringify(fragment)}\n`, "utf-8");
  }

  private async maybeWriteShortTermSnapshot(sceneId: string): Promise<void> {
    const nextCount = (this._sceneSyncCounters.get(sceneId) || 0) + 1;
    this._sceneSyncCounters.set(sceneId, nextCount);

    if (nextCount % this._snapshotEveryRecords !== 0) {
      return;
    }

    const snapshot = MemoryRepository.instance.getShortTermSceneSnapshot(sceneId, this._snapshotRecentLimit);
    const safeSceneId = this.sanitizeSceneId(sceneId);
    const snapshotPath = path.join(this._shortTermSnapshotDir, `${safeSceneId}.json`);
    const payload = {
      scene_id: snapshot.scene_id,
      total_records: snapshot.total_records,
      latest_timestamp: snapshot.latest_timestamp,
      recent_limit: this._snapshotRecentLimit,
      generated_at: new Date().toISOString(),
      records: snapshot.recent_records,
    };

    await fs.writeJson(snapshotPath, payload, { spaces: 2 });
    logger.debug("短期记忆场景快照已刷新", {
      scene_id: sceneId,
      snapshot_path: snapshotPath,
      total_records: snapshot.total_records,
      recent_records: snapshot.recent_records.length,
    });
  }

  private sanitizeSceneId(sceneId: string): string {
    return sceneId.replace(/[^a-zA-Z0-9._-]/g, "_");
  }
}
