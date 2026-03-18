const path = require("path");
const fs = require("fs");

class Live2DActionAdapterPlugin {
  constructor() {
    this.kernelProxy = null;
    this.handlers = new Map();
    this.outputPath = "";
  }

  async onInit() {
    if (!this.kernelProxy) {
      throw new Error("Kernel proxy 未注入");
    }

    const outputDir = path.resolve(process.cwd(), "runtime", "live2d");
    fs.mkdirSync(outputDir, { recursive: true });
    this.outputPath = path.join(outputDir, "action-stream.jsonl");

    this.kernelProxy.log("info", "Live2D 动作流适配器初始化完成", {
      output_path: this.outputPath,
    });
  }

  async onStart() {
    if (!this.kernelProxy) {
      throw new Error("Kernel proxy 未注入");
    }

    await this.subscribe("ActionStreamStartedEvent");
    await this.subscribe("ActionStreamChunkEvent");
    await this.subscribe("ActionStreamCompletedEvent");
    await this.subscribe("ActionStreamCancelledEvent");

    this.kernelProxy.log("info", "Live2D 动作流适配器已启动");
  }

  async onStop() {
    if (!this.kernelProxy) {
      return;
    }

    for (const [eventType, handler] of this.handlers.entries()) {
      try {
        await this.kernelProxy.unsubscribeEvent(eventType, handler);
      } catch (error) {
        const message = error && error.message ? error.message : String(error);
        this.kernelProxy.log("warn", "取消订阅失败", { event_type: eventType, error: message });
      }
    }
    this.handlers.clear();
    this.kernelProxy.log("info", "Live2D 动作流适配器已停止");
  }

  async subscribe(eventType) {
    const handler = async (event) => {
      await this.appendEvent(eventType, event);
    };
    this.handlers.set(eventType, handler);
    await this.kernelProxy.subscribeEvent(eventType, handler);
  }

  async appendEvent(eventType, event) {
    const line = JSON.stringify({
      event_type: eventType,
      occurred_at: Date.now(),
      payload: event && event.payload ? event.payload : event,
      trace_id: event && event.trace_context ? event.trace_context.trace_id : "",
    });

    await fs.promises.appendFile(this.outputPath, `${line}\n`, "utf8");
  }
}

module.exports = Live2DActionAdapterPlugin;
module.exports.default = Live2DActionAdapterPlugin;
