function normalizeMessageSegments(message, rawMessage) {
  if (Array.isArray(message)) {
    return message
      .filter((segment) => segment && typeof segment === "object" && typeof segment.type === "string")
      .map((segment) => ({
        type: String(segment.type),
        data: segment.data && typeof segment.data === "object" ? segment.data : {},
      }));
  }

  if (typeof message === "string") {
    const text = message.trim();
    return text ? [{ type: "text", data: { text } }] : [];
  }

  if (typeof rawMessage === "string") {
    const text = rawMessage.trim();
    return text ? [{ type: "text", data: { text } }] : [];
  }

  return [];
}

function toObject(value) {
  if (!value) {
    return null;
  }
  if (typeof value === "object") {
    return value;
  }
  if (typeof value === "string") {
    try {
      const parsed = JSON.parse(value);
      return parsed && typeof parsed === "object" ? parsed : null;
    } catch (_error) {
      return null;
    }
  }
  return null;
}

function normalizeOneEvent(candidate) {
  if (!candidate || typeof candidate !== "object") {
    return null;
  }

  if (candidate.echo && Object.prototype.hasOwnProperty.call(candidate, "status")) {
    return candidate;
  }

  if (!candidate.post_type) {
    return null;
  }

  if (candidate.post_type !== "message") {
    return candidate;
  }

  const normalizedSegments = normalizeMessageSegments(candidate.message, candidate.raw_message);
  return {
    ...candidate,
    message: normalizedSegments,
    message_format: "array",
  };
}

function extractCandidates(frame) {
  const base = toObject(frame);
  if (!base) {
    return [];
  }

  if (base.arrayMsg || base.stringMsg) {
    const list = [];
    const arrayMsg = toObject(base.arrayMsg);
    const stringMsg = toObject(base.stringMsg);
    if (arrayMsg) {
      list.push(arrayMsg);
    }
    if (stringMsg) {
      list.push(stringMsg);
    }
    return list;
  }

  const payload = toObject(base.payload);
  if (payload && (payload.arrayMsg || payload.stringMsg || payload.post_type)) {
    const list = [];
    const arrayMsg = toObject(payload.arrayMsg);
    const stringMsg = toObject(payload.stringMsg);
    if (arrayMsg) {
      list.push(arrayMsg);
    }
    if (stringMsg) {
      list.push(stringMsg);
    }
    if (list.length > 0) {
      return list;
    }
    if (payload.post_type) {
      return [payload];
    }
  }

  const data = toObject(base.data);
  if (data && (data.arrayMsg || data.stringMsg || data.post_type)) {
    const list = [];
    const arrayMsg = toObject(data.arrayMsg);
    const stringMsg = toObject(data.stringMsg);
    if (arrayMsg) {
      list.push(arrayMsg);
    }
    if (stringMsg) {
      list.push(stringMsg);
    }
    if (list.length > 0) {
      return list;
    }
    if (data.post_type) {
      return [data];
    }
  }

  const event = toObject(base.event);
  if (event && event.post_type) {
    return [event];
  }

  if (base.post_type || (base.echo && Object.prototype.hasOwnProperty.call(base, "status"))) {
    return [base];
  }

  if (typeof base.message === "string") {
    const maybe = toObject(base.message);
    if (maybe && (maybe.post_type || maybe.arrayMsg || maybe.stringMsg)) {
      return extractCandidates(maybe);
    }
  }

  return [];
}

function normalizeOB11Frames(rawPayload) {
  const frames = Array.isArray(rawPayload) ? rawPayload : [rawPayload];
  const normalized = [];

  for (const frame of frames) {
    const candidates = extractCandidates(frame);
    for (const candidate of candidates) {
      const event = normalizeOneEvent(candidate);
      if (!event) {
        continue;
      }
      normalized.push(event);
      // 遇到 message 事件时优先使用 arrayMsg，避免 stringMsg 重复入站。
      if (event.post_type === "message") {
        break;
      }
    }
  }

  return normalized;
}

module.exports = {
  normalizeOB11Frames,
};
