import { getLogger } from "../../foundation/logger/logger";
import { PerceptionMessageRequest } from "@cradle-selrena/protocol";

const logger = getLogger("channel-runtime");

export class ChannelRuntimeManager {
  private static _instance: ChannelRuntimeManager | null = null;
  
  private constructor() {}

  public static get instance(): ChannelRuntimeManager {
    if (!this._instance) {
      this._instance = new ChannelRuntimeManager();
    }
    return this._instance;
  }

  public async handleInboundMessage(req: PerceptionMessageRequest): Promise<void> {
    logger.info(`Received inbound message: ${req.id} from ${req.source}`);
    // Here we will hook into SelrenaAttentionPolicy or PerceptionSessionManager
  }
}
