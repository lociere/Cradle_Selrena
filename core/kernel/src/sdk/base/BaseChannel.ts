import { BasePlugin } from "./BasePlugin";
import { PerceptionMessageRequest } from "@cradle-selrena/protocol";

export abstract class BaseChannel extends BasePlugin {
  protected async submitMessage(message: PerceptionMessageRequest): Promise<any> {
    return this.context.proxy.submitChannelMessage(message);
  }
}
