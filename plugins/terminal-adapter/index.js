/**
 * 终端适配器插件（最简示例）
 *
 * 该插件仅用于验证内核插件机制是否可用，功能为在终端中输入并发送给 AI。
 */

class TerminalAdapterPlugin {
  constructor() {
    /** @type {import("@cradle-selrena/protocol").IKernelProxy | null} */
    this.kernelProxy = null;
    this.ready = false;
  }

  async onInit() {
    if (!this.kernelProxy) {
      throw new Error("Kernel proxy 未注入");
    }
    this.kernelProxy.log("info", "TerminalAdapterPlugin init");
  }

  async onStart() {
    if (!this.kernelProxy) {
      throw new Error("Kernel proxy 未注入");
    }
    this.ready = true;
    this.kernelProxy.log("info", "TerminalAdapterPlugin started");

    // 监听所有事件，以示范订阅能力（可选）
    await this.kernelProxy.subscribeEvent("*", async (event) => {
      // 仅打印事件类型
      this.kernelProxy.log("debug", "收到事件", { event_type: event.event_type });
    });
  }

  async onStop() {
    this.ready = false;
    if (this.kernelProxy) {
      this.kernelProxy.log("info", "TerminalAdapterPlugin stopped");
    }
  }
}

module.exports = TerminalAdapterPlugin;
module.exports.default = TerminalAdapterPlugin;
