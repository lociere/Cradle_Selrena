const readline = require("readline");

/**
 * 终端交互适配器插件
 * - 真实模式：监听 stdin，输入文本后转发给 AI 并打印回复
 * - Smoke 模式：设置环境变量 TERMINAL_ADAPTER_SMOKE_MESSAGE 后自动发一条测试消息
 */
class TerminalAdapterPlugin {
  constructor() {
    /** @type {import("@cradle-selrena/protocol").IKernelProxy | null} */
    this.kernelProxy = null;
    /** @type {import("readline").Interface | null} */
    this.rl = null;
    this.ready = false;
    this.isInteractiveTTY = false;
    this.promptText = "you> ";
    this.sceneId = "master-terminal";
  }

  renderPrompt() {
    if (this.rl && this.ready) {
      if (this.isInteractiveTTY) {
        this.rl.prompt(true);
      } else {
        process.stdout.write(this.promptText);
      }
    }
  }

  printMessage(prefix, message, isError = false) {
    if (this.rl) {
      this.rl.pause();
    }

    const output = `${prefix}: ${message}`;
    if (isError) {
      console.error(output);
    } else {
      console.log(output);
    }

    if (this.rl) {
      this.rl.resume();
    }
    this.renderPrompt();
  }

  async onInit() {
    if (!this.kernelProxy) {
      throw new Error("Kernel proxy 未注入");
    }
    this.kernelProxy.log("info", "终端适配器插件初始化完成", { scene_id: this.sceneId });
  }

  async onStart() {
    if (!this.kernelProxy) {
      throw new Error("Kernel proxy 未注入");
    }

    const hasInteractiveTTY = Boolean(process.stdin.isTTY && process.stdout.isTTY);
    this.isInteractiveTTY = hasInteractiveTTY;

    if (!process.stdin.readable) {
      this.ready = false;
      this.kernelProxy.log("warn", "终端适配器未检测到可读 stdin，交互模式不可用", {
        stdin_readable: Boolean(process.stdin.readable),
        stdin_is_tty: Boolean(process.stdin.isTTY),
        stdout_is_tty: Boolean(process.stdout.isTTY),
      });
      return;
    }

    this.ready = true;
    this.kernelProxy.log("info", "终端适配器插件启动成功", {
      hint: hasInteractiveTTY
        ? "输入内容即可与月见对话，输入 exit/quit 退出"
        : "已启用非TTY兼容交互模式，输入内容后回车与月见对话，输入 exit/quit 退出",
      interactive_tty: hasInteractiveTTY,
    });

    const smoke = process.env.TERMINAL_ADAPTER_SMOKE_MESSAGE;
    if (smoke && smoke.trim()) {
      await this.runSmoke(smoke.trim());
      return;
    }

    process.stdin.setEncoding("utf8");
    process.stdin.resume();

    this.rl = readline.createInterface({
      input: process.stdin,
      output: process.stdout,
      prompt: hasInteractiveTTY ? this.promptText : "",
      terminal: hasInteractiveTTY,
      historySize: 100,
    });

    console.log("\n===== 月见 Selrena 终端交互模式 =====");
    console.log(`输入内容后在 ${this.promptText.trim()} 处回车即可对话，输入 exit 或 quit 退出。\n`);
    this.renderPrompt();

    this.rl.on("line", async (input) => {
      const text = (input || "").trim();
      if (!text) {
        this.renderPrompt();
        return;
      }

      if (text.toLowerCase() === "exit" || text.toLowerCase() === "quit") {
        this.kernelProxy.log("info", "终端适配器收到退出指令");
        this.rl && this.rl.close();
        process.exit(0);
        return;
      }

      await this.sendAndPrint(text);
    });

    this.rl.on("SIGINT", () => {
      this.kernelProxy.log("info", "终端适配器收到中断信号");
      this.rl && this.rl.close();
    });

    this.rl.on("close", () => {
      this.ready = false;
      this.kernelProxy && this.kernelProxy.log("info", "终端交互已关闭");
    });
  }

  async runSmoke(text) {
    this.kernelProxy.log("info", "终端适配器进入 smoke 模式", { text });
    await this.sendAndPrint(text);
    // 给跨进程异步事件（例如记忆同步）预留短暂刷新窗口。
    await new Promise((resolve) => setTimeout(resolve, 300));
    this.kernelProxy.log("info", "终端适配器 smoke 模式完成，进程退出");
    process.exit(0);
  }

  async sendAndPrint(text) {
    try {
      const response = await this.kernelProxy.sendChatMessage(text, this.sceneId, 10);
      const reply = response && (response.reply_content || response.content || "");
      this.printMessage("月见", reply || "...", false);
      this.kernelProxy.log("info", "终端对话完成", { input: text, has_reply: Boolean(reply) });
    } catch (error) {
      const message = error && error.message ? error.message : String(error);
      this.printMessage("月见", `抱歉，处理失败：${message}`, true);
      this.kernelProxy.log("error", "终端对话失败", { input: text, error: message });
    }
  }

  async onStop() {
    this.ready = false;
    if (this.rl) {
      this.rl.close();
      this.rl = null;
    }
    if (this.kernelProxy) {
      this.kernelProxy.log("info", "终端适配器插件已停止");
    }
  }
}

module.exports = TerminalAdapterPlugin;
module.exports.default = TerminalAdapterPlugin;
