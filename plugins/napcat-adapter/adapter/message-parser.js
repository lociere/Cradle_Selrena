function guessMimeType(type, uri) {
  const lower = String(uri || "").toLowerCase();
  if (type === "image") {
    if (lower.endsWith(".png")) return "image/png";
    if (lower.endsWith(".webp")) return "image/webp";
    if (lower.endsWith(".gif")) return "image/gif";
    return "image/jpeg";
  }
  if (type === "video") {
    if (lower.endsWith(".webm")) return "video/webm";
    if (lower.endsWith(".mov")) return "video/quicktime";
    return "video/mp4";
  }
  return "application/octet-stream";
}

function classifySpecialImage(data) {
  const summary = String(data.summary || "");
  const file = String(data.file || "");
  const hint = `${summary} ${file}`;
  if (/标准表情|表情|sticker|mface|emoji/i.test(hint)) {
    return "sticker";
  }
  return "image";
}

function parseMessageSegments(event, botSelfId, config) {
  if (!event || event.post_type !== "message") {
    throw new Error("invalid ob11 message event");
  }
  if (!event.message_type || !event.user_id) {
    throw new Error("missing required ob11 message fields");
  }

  const segments = Array.isArray(event.message) ? event.message : [];
  const textParts = [];
  const mediaItems = [];

  let hasMention = false;
  let hasReply = false;
  let hasFace = false;
  let hasSticker = false;
  let hasImage = false;
  let hasVideo = false;
  let replyMessageId = "";
  let recordSource = "";

  for (const segment of segments) {
    if (!segment || typeof segment !== "object") {
      continue;
    }
    const type = segment.type;
    const data = segment.data || {};

    if (type === "text") {
      textParts.push(String(data.text || ""));
      continue;
    }

    if (type === "at") {
      const qq = String(data.qq || "");
      textParts.push(`@${qq}`);
      if (qq && qq === String(botSelfId || "")) {
        hasMention = true;
      }
      continue;
    }

    if (type === "reply") {
      hasReply = true;
      replyMessageId = String(data.id || "");
      continue;
    }

    if (type === "face") {
      hasFace = true;
      textParts.push("[QQ表情]");
      continue;
    }

    if (type === "record") {
      recordSource = String(data.file || data.path || data.url || "");
      continue;
    }

    if (type === "image") {
      const uri = String(data.url || data.file || data.path || "");
      const imageKind = classifySpecialImage(data);
      if (imageKind === "sticker") {
        hasSticker = true;
        textParts.push("[表情包]");
      } else {
        hasImage = true;
        textParts.push("[图片]");
      }
      if (uri && config.ingress.multimodal && config.ingress.multimodal.enabled) {
        mediaItems.push({
          modality: "image",
          uri,
          mime_type: guessMimeType("image", uri),
          description_hint: String(data.summary || ""),
          metadata: {
            file_size: data.file_size,
            visual_kind: imageKind,
          },
        });
      }
      continue;
    }

    if (type === "video") {
      const uri = String(data.url || data.file || data.path || "");
      hasVideo = true;
      textParts.push("[视频]");
      if (uri && config.ingress.multimodal && config.ingress.multimodal.enabled) {
        mediaItems.push({
          modality: "video",
          uri,
          mime_type: guessMimeType("video", uri),
          description_hint: String(data.summary || ""),
          metadata: {
            file_size: data.file_size,
          },
        });
      }
      continue;
    }

    if (type === "file") {
      textParts.push(`[文件:${String(data.name || data.file || "未知文件")}]`);
    }
  }

  const sourceType = event.message_type === "group" ? "group" : "private";
  const sourceId = sourceType === "group" ? String(event.group_id || "") : String(event.user_id || "");
  const senderId = String(event.user_id || "");
  const sceneId = `napcat:${sourceType}:${sourceId}`;
  const displayText = String(event.raw_message || textParts.join("")).trim();

  return {
    sourceType,
    sourceId,
    senderId,
    sceneId,
    displayText,
    text: textParts.join("").trim(),
    recordSource,
    mediaItems,
    replyMessageId,
    hasMention,
    messageTraits: {
      isAtMessage: hasMention,
      isReplyMessage: hasReply,
      hasFace,
      hasSticker,
      hasImage,
      hasVideo,
    },
  };
}

module.exports = {
  parseMessageSegments,
};
