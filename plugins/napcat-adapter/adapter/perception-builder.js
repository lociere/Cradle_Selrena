function cleanInboundText(text, event, config, botSelfId) {
  let value = String(text || "").replace(/\r/g, "").trim();
  if (!value) {
    return value;
  }

  if (event.message_type === "group" && config.ingress.strip_self_mention) {
    const selfId = String(event.self_id || botSelfId || "");
    if (selfId) {
      const mentionPattern = new RegExp(`@${selfId}\\s*`, "g");
      value = value.replace(mentionPattern, "").trim();
    }
  }

  if (config.ingress.strip_leading_wake_words) {
    for (const wakeWord of config.ingress.wake_words) {
      if (!wakeWord) {
        continue;
      }
      if (value.startsWith(wakeWord)) {
        value = value.slice(wakeWord.length).trim();
        break;
      }
    }
  }

  return value;
}

function shouldDispatchGroupMessage(parsed, originalText, config) {
  const policy = config.ingress.group_policy;
  const normalized = String(originalText || "").toLowerCase();
  const hasWakeWord = config.ingress.wake_words.some((wakeWord) => {
    const keyword = String(wakeWord || "").trim().toLowerCase();
    return keyword && normalized.includes(keyword);
  });

  if (policy === "all") {
    return true;
  }
  if (policy === "mention_only") {
    return parsed.messageTraits.isAtMessage;
  }
  if (policy === "wake_word_only") {
    return hasWakeWord;
  }
  return parsed.messageTraits.isAtMessage || hasWakeWord;
}

function buildTextPayload(parsed, nickname, cleanText) {
  const labels = [];
  if (parsed.messageTraits.isAtMessage) labels.push("@消息");
  if (parsed.messageTraits.isReplyMessage) labels.push("回复消息");
  if (parsed.messageTraits.hasSticker) labels.push("表情包");
  if (parsed.messageTraits.hasFace) labels.push("QQ表情");
  if (parsed.messageTraits.hasImage) labels.push("图片");
  if (parsed.messageTraits.hasVideo) labels.push("视频");

  const traits = labels.length > 0 ? labels.join("/") : "普通消息";
  const senderTag = parsed.sourceType === "group"
    ? `[群成员:${nickname}(${parsed.senderId})]`
    : `[私聊用户:${nickname}(${parsed.senderId})]`;
  const replyTag = parsed.replyMessageId ? `[回复ID:${parsed.replyMessageId}]` : "";

  const lines = [senderTag, `[消息类型:${traits}]`, replyTag, cleanText].filter(Boolean);
  return lines.join(" ").trim();
}

function buildPerceptionRequest(parsed, nickname, cleanText, config, isMainUser) {
  const inputItems = [];
  const textPayload = buildTextPayload(parsed, nickname, cleanText);
  if (textPayload) {
    inputItems.push({
      modality: "text",
      text: textPayload,
      metadata: {
        sender_id: parsed.senderId,
        sender_nickname: nickname,
        message_traits: parsed.messageTraits,
        is_main_user: isMainUser,
      },
    });
  }

  if (parsed.mediaItems && parsed.mediaItems.length > 0) {
    inputItems.push(...parsed.mediaItems.map((item) => ({
      ...item,
      metadata: {
        ...(item.metadata || {}),
        sender_id: parsed.senderId,
        sender_nickname: nickname,
        message_traits: parsed.messageTraits,
        is_main_user: isMainUser,
      },
    })));
  }

  if (inputItems.length === 0) {
    return null;
  }

  return {
    input: {
      items: inputItems,
    },
    scene_id: parsed.sceneId,
    familiarity: parsed.sourceType === "group"
      ? Number(config.ingress.familiarity.group || 0)
      : Number(config.ingress.familiarity.private || 0),
    source: {
      vessel_id: "napcat-adapter",
      source_type: parsed.sourceType,
      source_id: parsed.sourceId,
    },
  };
}

module.exports = {
  cleanInboundText,
  shouldDispatchGroupMessage,
  buildPerceptionRequest,
};
