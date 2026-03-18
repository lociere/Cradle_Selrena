const path = require("path");
const { WebSocketServer } = require("ws");
const { loadNapcatConfig } = require("./config");
const { parseMessageSegments } = require("../adapter/message-parser");
const { normalizeOB11Frames } = require("../adapter/ob11-normalizer");
const { SenderProfileResolver } = require("../adapter/profile-resolver");
const {
  cleanInboundText,
  cleanOutboundReply,
  shouldDispatchGroupMessage,
  buildPerceptionRequest,
} = require("../adapter/perception-builder");

class NapcatAdapterPlugin {
  constructor() {
    /** @type {import("@cradle-selrena/protocol").IKernelProxy | null} */
    this.kernelProxy = null;
    this.server = null;
    this.socket = null;
    this.pendingActions = new Map();
    this.config = null;
    this.configPath = "";
    this.botSelfId = "";
    this.profileResolver = null;
    this.repoRoot = path.resolve(__dirname, "..", "..", "..");
  }

  async onInit() {
    this.ensureKernelProxy();
    const loaded = loadNapcatConfig();
    this.config = loaded.config;
    this.configPath = loaded.configPath;

    this.profileResolver = new SenderProfileResolver(
      this.kernelProxy,
      this.callAction.bind(this),
      this.config.runtime.nickname_cache_ttl_ms
    );

    if (!String(this.config.main_user.qq || "").trim()) {
      this.kernelProxy.log("warn", "Napcat 未配置 main_user.qq，私聊会话将默认归入 external_users 命名空间，群聊仍按场景归档");
    }

    this.kernelProxy.log("info", "Napcat 适配器初始化完成", {
      config_path: this.configPath,
      ws_host: this.config.transport.host,
      ws_port: this.config.transport.port,
      ws_path: this.config.transport.path,
      main_user_qq: this.config.main_user.qq || "",
    });
  }

  async onStart() {
    this.ensureKernelProxy();
    if (!this.config.enabled) {
      this.kernelProxy.log("warn", "Napcat 适配器已禁用，跳过启动");
      return;
    }
    await this.startReverseWebSocketServer();
  }

  async onStop() {
    for (const pending of this.pendingActions.values()) {
      clearTimeout(pending.timer);
      pending.reject(new Error("Napcat 适配器停止，动作已取消"));
    }
    this.pendingActions.clear();

    if (this.socket) {
      this.socket.removeAllListeners();
      this.socket.close();
      this.socket = null;
    }

    if (this.server) {
      await new Promise((resolve, reject) => {
        this.server.close((error) => (error ? reject(error) : resolve()));
      });
      this.server = null;
    }

    if (this.kernelProxy) {
      this.kernelProxy.log("info", "Napcat 适配器已停止");
    }
  }

  ensureKernelProxy() {
    if (!this.kernelProxy) {
      throw new Error("Kernel proxy 未注入");
    }
  }

  async startReverseWebSocketServer() {
    const { host, port, path: wsPath } = this.config.transport;
    await new Promise((resolve, reject) => {
      const server = new WebSocketServer({ host, port, path: wsPath });
      this.server = server;

      server.once("listening", () => {
        this.kernelProxy.log("info", "Napcat 反向 WebSocket 服务已启动，等待客户端接入", {
          host,
          port,
          path: wsPath,
        });
        resolve();
      });

      server.once("error", (error) => reject(error));

      server.on("connection", (socket, request) => {
        if (!this.isAuthorized(request)) {
          this.kernelProxy.log("warn", "Napcat 客户端鉴权失败，连接已拒绝", {
            remote_address: request.socket.remoteAddress,
          });
          socket.close(1008, "unauthorized");
          return;
        }

        if (this.socket && this.socket !== socket) {
          this.socket.close(1000, "replaced by new connection");
        }

        this.socket = socket;
        this.kernelProxy.log("info", "Napcat 客户端已连接", {
          remote_address: request.socket.remoteAddress,
        });

        socket.on("message", async (buffer) => {
          try {
            await this.handleSocketPayload(buffer.toString());
          } catch (error) {
            this.kernelProxy.log("error", "Napcat 消息处理失败", {
              error: error instanceof Error ? error.message : String(error),
            });
          }
        });

        socket.on("close", (code, reason) => {
          if (this.socket === socket) {
            this.socket = null;
          }
          this.kernelProxy.log("warn", "Napcat 客户端连接关闭", {
            code,
            reason: reason ? reason.toString() : "",
          });
        });

        socket.on("error", (error) => {
          this.kernelProxy.log("error", "Napcat 客户端连接异常", {
            error: error.message,
          });
        });
      });
    });
  }

  isAuthorized(request) {
    const expectedToken = this.config.transport.access_token;
    if (!expectedToken) {
      return true;
    }

    const authHeader = request.headers.authorization || "";
    const headerToken = authHeader.startsWith("Bearer ") ? authHeader.slice(7) : "";
    const url = new URL(request.url || this.config.transport.path, `ws://${request.headers.host || "127.0.0.1"}`);
    const queryToken = url.searchParams.get("access_token") || "";

    return headerToken === expectedToken || queryToken === expectedToken;
  }

  async handleSocketPayload(payload) {
    if (!payload) return;

    const raw = JSON.parse(payload);
    const frames = normalizeOB11Frames(raw);

    if (frames.length === 0) {
      const rawKeys = raw && typeof raw === "object" ? Object.keys(raw).slice(0, 12) : [];
      this.kernelProxy.log("debug", "Napcat 入站帧未识别为 OB11 事件", {
        raw_type: Array.isArray(raw) ? "array" : typeof raw,
        raw_keys: rawKeys,
        payload_size: payload.length,
      });
      return;
    }

    this.kernelProxy.log("debug", "Napcat 入站帧归一化完成", {
      normalized_count: frames.length,
      post_types: frames.map((item) => item.post_type || "unknown").slice(0, 10),
    });

    for (const message of frames) {
      if (!message || typeof message !== "object") {
        continue;
      }

      if (message.echo && Object.prototype.hasOwnProperty.call(message, "status")) {
        this.resolvePendingAction(message);
        continue;
      }

      if (message.self_id) {
        this.botSelfId = String(message.self_id);
      }

      if (message.post_type === "meta_event") {
        this.handleMetaEvent(message);
        continue;
      }

      if (message.post_type !== "message") {
        continue;
      }

      await this.handleIncomingMessage(message);
    }
  }

  resolvePendingAction(message) {
    const key = String(message.echo || "");
    const pending = this.pendingActions.get(key);
    if (!pending) {
      return;
    }

    clearTimeout(pending.timer);
    this.pendingActions.delete(key);

    if (message.status === "ok" && Number(message.retcode || 0) === 0) {
      pending.resolve(message.data || {});
      return;
    }
    pending.reject(new Error(message.message || message.wording || "Napcat 动作执行失败"));
  }

  handleMetaEvent(event) {
    if (event.meta_event_type === "lifecycle") {
      this.kernelProxy.log("info", "Napcat 生命周期事件", {
        sub_type: event.sub_type,
        self_id: event.self_id,
      });
      return;
    }

    if (event.meta_event_type === "heartbeat") {
      const status = event.status || {};
      this.kernelProxy.logState("debug", "napcat-heartbeat", {
        self_id: event.self_id,
        interval: event.interval,
        online: Boolean(status.online),
        good: Boolean(status.good),
      }, "Napcat 心跳状态变更", {
        self_id: event.self_id,
        interval: event.interval,
        status: event.status,
      });
    }
  }

  shouldIgnore(parsed) {
    if (this.config.ingress.ignore_self && String(this.botSelfId || "") === parsed.senderId) {
      return true;
    }
    if (parsed.sourceType === "private" && !this.config.ingress.private_enabled) {
      return true;
    }
    if (parsed.sourceType === "group" && !this.config.ingress.group_enabled) {
      return true;
    }
    if (this.config.ingress.blocked_user_ids.includes(parsed.senderId)) {
      return true;
    }
    if (parsed.sourceType === "group" && this.config.ingress.blocked_group_ids.includes(parsed.sourceId)) {
      return true;
    }
    return false;
  }

  isMainUser(senderId) {
    const configured = String(this.config.main_user.qq || "").trim();
    return configured.length > 0 && configured === String(senderId || "");
  }

  async buildPerceptionFromEvent(event) {
    const parsed = parseMessageSegments(event, this.botSelfId, this.config);
    if (this.shouldIgnore(parsed)) {
      return null;
    }

    let rawText = parsed.text;
    if (!rawText && this.config.speech.asr_for_record_enabled && parsed.recordSource) {
      try {
        const asr = await this.kernelProxy.recognizeSpeech({ audio_path: parsed.recordSource });
        if (asr && asr.status === "success" && asr.text) {
          rawText = String(asr.text).trim();
        }
      } catch (error) {
        this.kernelProxy.log("warn", "ASR 识别失败", {
          error: error instanceof Error ? error.message : String(error),
          record_source: parsed.recordSource,
        });
      }
    }

    const cleanText = cleanInboundText(rawText || "", event, this.config, this.botSelfId);
    if (parsed.sourceType === "group" && !shouldDispatchGroupMessage(parsed, rawText || cleanText, this.config)) {
      this.kernelProxy.log("debug", "Napcat 群聊消息被策略过滤", {
        source_type: parsed.sourceType,
        source_id: parsed.sourceId,
        sender_id: parsed.senderId,
        group_policy: this.config.ingress.group_policy,
        raw_text_preview: String(rawText || "").slice(0, 80),
      });
      return null;
    }

    const nickname = await this.profileResolver.resolve(event, parsed);
    const isMainUser = this.isMainUser(parsed.senderId);
    const sessionPolicy = this.getSessionPolicyBySourceType(parsed.sourceType);

    const scene = await this.kernelProxy.resolveScene({
      source: {
        vessel_id: "napcat-adapter",
        source_type: parsed.sourceType,
        source_id: parsed.sourceId,
      },
      routing: {
        session_policy: sessionPolicy,
        actor: {
          actor_id: parsed.senderId,
          actor_name: nickname,
        },
      },
    });

    const request = buildPerceptionRequest(
      parsed,
      scene.scene_id,
      nickname,
      cleanText,
      this.config,
      isMainUser,
      scene.session_policy
    );
    if (!request) {
      return null;
    }

    await this.appendTranscript({
      parsed,
      nickname,
      isMainUser,
      role: "user",
      content: parsed.displayText || rawText || cleanText,
      tags: this.buildTranscriptTags(parsed.messageTraits, isMainUser),
    });

    return {
      request,
      parsed,
      nickname,
      isMainUser,
    };
  }

  async handleIncomingMessage(event) {
    const payload = await this.buildPerceptionFromEvent(event);
    if (!payload) {
      return;
    }

    const { request, parsed, nickname, isMainUser } = payload;
    this.kernelProxy.log("info", "Napcat 消息已分类并送入核心", {
      scene_id: request.scene_id,
      source_type: request.source.source_type,
      source_id: request.source.source_id,
      sender_id: parsed.senderId,
      sender_nickname: nickname,
      is_main_user: isMainUser,
      traits: parsed.messageTraits,
    });

    const response = await this.kernelProxy.ingestPerceptionMessage(request);
    if (!response || !response.reply_content) {
      this.kernelProxy.log("debug", "Napcat 消息已并入注意力窗口，本次不直接回复", {
        scene_id: request.scene_id,
        sender_id: parsed.senderId,
      });
      return;
    }
    if (!this.config.reply.enabled) {
      return;
    }

    const rawReplyContent = String((response && response.reply_content) || "").trim();
    const replyContent = cleanOutboundReply(rawReplyContent);
    if (!replyContent) {
      this.kernelProxy.log("warn", "Napcat 回复在清洗情绪词后为空，跳过发送", {
        scene_id: request.scene_id,
      });
      return;
    }

    if (this.shouldSendVoiceReply(event)) {
      const sent = await this.sendVoiceReply(event, replyContent);
      if (sent) {
        await this.appendTranscript({
          parsed,
          nickname,
          isMainUser,
          role: "assistant",
          content: replyContent,
          tags: [isMainUser ? "对主用户" : "对外部联系人", "语音回复"],
        });
        return;
      }
    }

    await this.sendReply(event, replyContent);
    await this.appendTranscript({
      parsed,
      nickname,
      isMainUser,
      role: "assistant",
      content: replyContent,
      tags: [
        isMainUser ? "对主用户" : "对外部联系人",
        parsed.messageTraits && parsed.messageTraits.isReplyMessage ? "针对回复消息" : "普通回复",
      ],
    });
  }

  buildTranscriptTags(traits, isMainUser) {
    const tags = [isMainUser ? "主用户" : "外部联系人"];
    if (!traits || typeof traits !== "object") {
      return tags;
    }
    if (traits.isAtMessage) tags.push("@消息");
    if (traits.isReplyMessage) tags.push("回复");
    if (traits.hasSticker) tags.push("表情包");
    if (traits.hasFace) tags.push("QQ表情");
    if (traits.hasImage) tags.push("图片");
    if (traits.hasVideo) tags.push("视频");
    return tags;
  }

  async appendTranscript({ parsed, nickname, isMainUser, role, content, tags }) {
    await this.kernelProxy.appendSceneTranscript({
      root_dir: this.config.memory.root_dir,
      scene_scope: parsed.sourceType === "group" ? "group_scene" : "private_session",
      scene_type: parsed.sourceType,
      transcript_scene_id: parsed.sourceId,
      identity_scope: isMainUser ? "master_user" : "external_users",
      owner_id: parsed.senderId,
      owner_label: parsed.sourceType === "group"
        ? `group:${parsed.sourceId}`
        : `${nickname}(${parsed.senderId})`,
      summary: parsed.sourceType === "group"
        ? "该文件记录一个群场景内的连续对话转录。"
        : "该文件记录一个私聊对象的连续对话转录。",
      role,
      speaker: role === "assistant" ? "月见" : `${nickname}(${parsed.senderId})`,
      content,
      tags,
      occurred_at: new Date().toISOString(),
    });
  }

  getSessionPolicyBySourceType(sourceType) {
    const partition = this.config.routing && this.config.routing.session_partition
      ? this.config.routing.session_partition
      : {};
    const key = sourceType === "group" ? "group" : "private";
    const configured = String(partition[key] || "by_source").trim();
    return configured === "by_actor" ? "by_actor" : "by_source";
  }

  shouldSendVoiceReply(event) {
    if (!this.config.speech.tts_reply_enabled) return false;
    return event.message_type === "group"
      ? Boolean(this.config.speech.tts_reply_in_group)
      : Boolean(this.config.speech.tts_reply_in_private);
  }

  buildTTSOutputPath(event) {
    const outputDir = path.resolve(this.repoRoot, this.config.speech.tts_output_dir || "runtime/tts");
    const sourceType = event.message_type === "group" ? "group" : "private";
    const sourceId = sourceType === "group" ? String(event.group_id || "unknown") : String(event.user_id || "unknown");
    return path.join(outputDir, `napcat-${sourceType}-${sourceId}-${Date.now()}.wav`);
  }

  async sendVoiceReply(event, replyText) {
    try {
      const outputPath = this.buildTTSOutputPath(event);
      const ttsResult = await this.kernelProxy.synthesizeSpeech({ text: replyText, output_path: outputPath });
      if (!ttsResult || ttsResult.status !== "success" || !ttsResult.output_path) {
        this.kernelProxy.log("warn", "TTS 返回失败，回退文本回复", { tts_result: ttsResult });
        return false;
      }

      const params = {
        message_type: event.message_type,
        message: [{ type: "record", data: { file: ttsResult.output_path } }],
        auto_escape: false,
      };
      if (event.message_type === "group") {
        params.group_id = String(event.group_id);
      } else {
        params.user_id = String(event.user_id);
      }
      await this.callAction("send_msg", params);
      return true;
    } catch (error) {
      this.kernelProxy.log("warn", "语音回复发送失败，回退文本回复", {
        error: error instanceof Error ? error.message : String(error),
      });
      return false;
    }
  }

  buildReplyMessage(event, replyText) {
    if (event.message_type !== "group") {
      return replyText;
    }

    const segments = [];
    if (this.config.reply.quote_source_message && event.message_id) {
      segments.push({ type: "reply", data: { id: String(event.message_id) } });
    }
    if (this.config.reply.mention_sender_in_group && event.user_id) {
      segments.push({ type: "at", data: { qq: String(event.user_id) } });
      segments.push({ type: "text", data: { text: ` ${replyText}` } });
      return segments;
    }
    if (segments.length > 0) {
      segments.push({ type: "text", data: { text: replyText } });
      return segments;
    }
    return replyText;
  }

  async sendReply(event, replyText) {
    const params = {
      message_type: event.message_type,
      message: this.buildReplyMessage(event, replyText),
      auto_escape: this.config.reply.auto_escape,
    };
    if (event.message_type === "group") {
      params.group_id = String(event.group_id);
    } else {
      params.user_id = String(event.user_id);
    }
    await this.callAction("send_msg", params);
  }

  async callAction(action, params) {
    if (!this.socket || this.socket.readyState !== 1) {
      throw new Error("Napcat 客户端未连接，无法发送动作");
    }

    const echo = `napcat-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    const payload = JSON.stringify({ action, params, echo });
    const timeoutMs = Number(this.config.runtime.action_timeout_ms || 15000);

    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pendingActions.delete(echo);
        reject(new Error(`Napcat 动作超时: ${action}`));
      }, timeoutMs);

      this.pendingActions.set(echo, { resolve, reject, timer });
      this.socket.send(payload, (error) => {
        if (!error) {
          return;
        }
        clearTimeout(timer);
        this.pendingActions.delete(echo);
        reject(error);
      });
    });
  }
}

module.exports = NapcatAdapterPlugin;
module.exports.default = NapcatAdapterPlugin;
