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
  if (parsed.messageTraits.isReplyToSelf) labels.push("回复月见");
  if (parsed.messageTraits.hasSticker) labels.push("表情包");
  if (parsed.messageTraits.hasFace) labels.push("QQ表情");
  if (parsed.messageTraits.hasImage) labels.push("图片");
  if (parsed.messageTraits.hasVideo) labels.push("视频");

  const traits = labels.length > 0 ? labels.join("/") : "普通消息";
  const senderTag = parsed.sourceType === "group"
    ? `[群成员:${nickname}(${parsed.senderId})]`
    : `[私聊用户:${nickname}(${parsed.senderId})]`;
  const replyTag = parsed.replyMessageId ? `[回复ID:${parsed.replyMessageId}]` : "";
  const replyTargetTag = parsed.replyContext && (parsed.replyContext.senderNickname || parsed.replyContext.senderId)
    ? `[回复对象:${parsed.replyContext.senderNickname || parsed.replyContext.senderId}(${parsed.replyContext.senderId || "unknown"})]`
    : "";
  const replyPreviewTag = parsed.replyContext && parsed.replyContext.previewText
    ? `[回复内容预览:${parsed.replyContext.previewText}]`
    : "";

  const lines = [senderTag, `[消息类型:${traits}]`, replyTag, replyTargetTag, replyPreviewTag, cleanText].filter(Boolean);
  return lines.join(" ").trim();
}

function buildPerceptionRequest(parsed, sceneId, nickname, cleanText, config, isMainUser, sessionPolicy = "by_source") {
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
        reply_context: parsed.replyContext,
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
        reply_context: parsed.replyContext,
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
    scene_id: sceneId,
    familiarity: parsed.sourceType === "group"
      ? Number(config.ingress.familiarity.group || 0)
      : Number(config.ingress.familiarity.private || 0),
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
  };
}

function cleanOutboundReply(text) {
  let value = String(text || "").replace(/\r/g, "").trim();
  if (!value) {
    return "";
  }

  const emotionWords = "开心|高兴|愉快|害羞|生气|愤怒|难过|委屈|傲娇|好奇|平静|冷静|happy|shy|angry|sulky|curious|sad|calm";
  const prefixPatterns = [
    new RegExp(`^[\\[\\(（【《<]\\s*(?:emotion|情绪)?\\s*[:：-]?\\s*(?:${emotionWords})\\s*[\\]\\)）】》>]\\s*`, "i"),
    new RegExp(`^(?:emotion|情绪)\\s*[:：-]\\s*(?:${emotionWords})\\s*`, "i"),
  ];

  let changed = true;
  while (changed && value) {
    changed = false;
    for (const pattern of prefixPatterns) {
      const nextValue = value.replace(pattern, "").trim();
      if (nextValue !== value) {
        value = nextValue;
        changed = true;
      }
    }
  }

  return value;
}

module.exports = {
  cleanInboundText,
  cleanOutboundReply,
  shouldDispatchGroupMessage,
  buildPerceptionRequest,
};
