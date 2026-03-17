class SenderProfileResolver {
  constructor(kernelProxy, callAction, cacheTtlMs) {
    this.kernelProxy = kernelProxy;
    this.callAction = callAction;
    this.cacheTtlMs = Number(cacheTtlMs || 300000);
    this.cache = new Map();
  }

  async resolve(event, parsed) {
    const cacheKey = `${parsed.sourceType}:${parsed.sourceId}:${parsed.senderId}`;
    const now = Date.now();

    const cached = this.cache.get(cacheKey);
    if (cached && cached.expiresAt > now) {
      return cached.value;
    }

    const sender = event.sender || {};
    let nickname = String(sender.card || sender.nickname || "").trim();

    if (!nickname) {
      nickname = await this.fetchNickname(event, parsed);
    }

    if (!nickname) {
      nickname = `QQ-${parsed.senderId || "unknown"}`;
    }

    this.cache.set(cacheKey, {
      value: nickname,
      expiresAt: now + this.cacheTtlMs,
    });

    return nickname;
  }

  async fetchNickname(event, parsed) {
    try {
      if (parsed.sourceType === "group") {
        const res = await this.callAction("get_group_member_info", {
          group_id: parsed.sourceId,
          user_id: parsed.senderId,
          no_cache: false,
        });
        return String((res && (res.card || res.nickname || (res.data && (res.data.card || res.data.nickname)))) || "").trim();
      }

      const res = await this.callAction("get_stranger_info", {
        user_id: parsed.senderId,
        no_cache: false,
      });
      return String((res && (res.nickname || (res.data && res.data.nickname))) || "").trim();
    } catch (error) {
      this.kernelProxy.log("warn", "获取发送者昵称失败，使用回退值", {
        source_type: parsed.sourceType,
        source_id: parsed.sourceId,
        sender_id: parsed.senderId,
        error: error instanceof Error ? error.message : String(error),
      });
      return "";
    }
  }
}

module.exports = {
  SenderProfileResolver,
};
