import { getLogger } from "../../foundation/logger/logger";
import { PerceptionMessageRequest } from "@cradle-selrena/protocol";

const logger = getLogger("channel-runtime");

export interface ChannelRuntimeSnapshot {
  source: string;
  firstSeenAt: number;
  lastSeenAt: number;
  messageCount: number;
  lastTraceId: string;
  lastSensoryType: PerceptionMessageRequest['sensoryType'];
  lastAddressMode: string;
  lastFamiliarity: number;
  lastTextPreview: string | null;
}

interface ChannelRuntimeState extends ChannelRuntimeSnapshot {}

export class ChannelRuntimeManager {
  private static _instance: ChannelRuntimeManager | null = null;
  private readonly _channels = new Map<string, ChannelRuntimeState>();
  
  private constructor() {}

  public static get instance(): ChannelRuntimeManager {
    if (!this._instance) {
      this._instance = new ChannelRuntimeManager();
    }
    return this._instance;
  }

  public async handleInboundMessage(req: PerceptionMessageRequest): Promise<ChannelRuntimeSnapshot> {
    const now = Date.now();
    const existing = this._channels.get(req.source);
    const nextState: ChannelRuntimeState = {
      source: req.source,
      firstSeenAt: existing?.firstSeenAt ?? now,
      lastSeenAt: now,
      messageCount: (existing?.messageCount ?? 0) + 1,
      lastTraceId: req.id,
      lastSensoryType: req.sensoryType,
      lastAddressMode: req.address_mode,
      lastFamiliarity: req.familiarity,
      lastTextPreview: req.content.text?.slice(0, 120) ?? null,
    };

    this._channels.set(req.source, nextState);

    logger.debug("通道运行态已更新", {
      source: nextState.source,
      message_count: nextState.messageCount,
      last_trace_id: nextState.lastTraceId,
      last_sensory_type: nextState.lastSensoryType,
    });

    return { ...nextState };
  }

  public getSnapshot(source: string): ChannelRuntimeSnapshot | null {
    const state = this._channels.get(source);
    return state ? { ...state } : null;
  }

  public listSnapshots(): ChannelRuntimeSnapshot[] {
    return Array.from(this._channels.values()).map((state) => ({ ...state }));
  }
}
