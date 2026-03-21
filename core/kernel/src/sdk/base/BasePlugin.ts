import { IBasePlugin, IKernelProxy } from "@cradle-selrena/protocol";
import { PluginContext } from "../context/PluginContext";
import { PluginLogger } from "../context/PluginLogger";

export abstract class BasePlugin implements IBasePlugin {
  public kernelProxy!: IKernelProxy;
  protected context!: PluginContext;
  protected logger!: PluginLogger;

  initContext(proxy: IKernelProxy, pluginId: string): void {
    this.kernelProxy = proxy;
    this.logger = new PluginLogger(proxy, pluginId);
    this.context = new PluginContext(proxy, this.logger);
  }

  async preLoad(): Promise<void> {}
  async onInit(): Promise<void> {}
  async onStart(): Promise<void> {}
  async onStop(): Promise<void> {}
  async onDestroy(): Promise<void> {}
}
