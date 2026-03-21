import { IKernelProxy } from "@cradle-selrena/protocol";
import { PluginLogger } from "./PluginLogger";

export class PluginContext {
  constructor(public readonly proxy: IKernelProxy, public readonly logger: PluginLogger) {}
  
  async getSelfConfig<T>(): Promise<T> {
    return this.proxy.getSelfConfig() as Promise<T>;
  }
}
