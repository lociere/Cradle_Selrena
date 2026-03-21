import { IKernelProxy } from "@cradle-selrena/protocol";

export class PluginLogger {
  constructor(private proxy: IKernelProxy, private prefix: string) {}

  info(msg: string, meta?: any) { this.proxy.log("info", `[${this.prefix}] ${msg}`, meta); }
  error(msg: string, meta?: any) { this.proxy.log("error", `[${this.prefix}] ${msg}`, meta); }
  warn(msg: string, meta?: any) { this.proxy.log("warn", `[${this.prefix}] ${msg}`, meta); }
  debug(msg: string, meta?: any) { this.proxy.log("debug", `[${this.prefix}] ${msg}`, meta); }
}
