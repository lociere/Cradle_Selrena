const fs = require("fs");
const path = require("path");
const yaml = require("yaml");

const DEFAULT_CONFIG = {
  enabled: true,
  transport: {
    host: "127.0.0.1",
    port: 6099,
    path: "/onebot/v11/ws",
    access_token: "",
    access_token_env: "NAPCAT_ACCESS_TOKEN",
    token_from_secrets: true,
  },
  main_user: {
    qq: "",
  },
  ingress: {
    ignore_self: true,
    private_enabled: true,
    group_enabled: true,
    group_policy: "wake_word_only",
    wake_words: ["月见", "Selrena", "selrena"],
    strip_self_mention: true,
    strip_leading_wake_words: true,
    blocked_user_ids: [],
    blocked_group_ids: [],
    familiarity: {
      private: 10,
      group: 6,
    },
    multimodal: {
      enabled: true,
    },
  },
  reply: {
    enabled: true,
    mention_sender_in_group: false,
    quote_source_message: false,
    auto_escape: false,
  },
  speech: {
    asr_for_record_enabled: true,
    asr_fallback_text: "",
    tts_reply_enabled: false,
    tts_reply_in_group: false,
    tts_reply_in_private: false,
    tts_output_dir: "runtime/tts",
  },
  memory: {
    enabled: true,
    root_dir: "data/memory/adapters/napcat",
    max_scene_records: 80,
  },
  routing: {
    session_partition: {
      private: "by_source",
      group: "by_source",
    },
  },
  runtime: {
    action_timeout_ms: 15000,
    nickname_cache_ttl_ms: 300000,
  },
};

function mergeConfig(baseConfig, overrideConfig) {
  return {
    ...baseConfig,
    ...overrideConfig,
    transport: {
      ...baseConfig.transport,
      ...(overrideConfig.transport || {}),
    },
    main_user: {
      ...baseConfig.main_user,
      ...(overrideConfig.main_user || {}),
    },
    ingress: {
      ...baseConfig.ingress,
      ...(overrideConfig.ingress || {}),
      familiarity: {
        ...baseConfig.ingress.familiarity,
        ...((overrideConfig.ingress && overrideConfig.ingress.familiarity) || {}),
      },
      multimodal: {
        ...baseConfig.ingress.multimodal,
        ...((overrideConfig.ingress && overrideConfig.ingress.multimodal) || {}),
      },
    },
    reply: {
      ...baseConfig.reply,
      ...(overrideConfig.reply || {}),
    },
    speech: {
      ...baseConfig.speech,
      ...(overrideConfig.speech || {}),
    },
    memory: {
      ...baseConfig.memory,
      ...(overrideConfig.memory || {}),
    },
    routing: {
      ...baseConfig.routing,
      ...(overrideConfig.routing || {}),
      session_partition: {
        ...baseConfig.routing.session_partition,
        ...((overrideConfig.routing && overrideConfig.routing.session_partition) || {}),
      },
    },
    runtime: {
      ...baseConfig.runtime,
      ...(overrideConfig.runtime || {}),
    },
  };
}

function normalizePath(value) {
  if (!value) {
    return "/";
  }
  return value.startsWith("/") ? value : `/${value}`;
}

function resolveAccessToken(transportConfig, secretsPath) {
  if (transportConfig.access_token) {
    return String(transportConfig.access_token);
  }

  const envName = transportConfig.access_token_env;
  if (envName && process.env[envName]) {
    return String(process.env[envName]);
  }

  if (!transportConfig.token_from_secrets || !fs.existsSync(secretsPath)) {
    return "";
  }

  try {
    const secrets = yaml.parse(fs.readFileSync(secretsPath, "utf8")) || {};
    return String(secrets.napcat && secrets.napcat.token ? secrets.napcat.token : "");
  } catch (_error) {
    return "";
  }
}

function loadNapcatConfig() {
  const repoRoot = path.resolve(__dirname, "..", "..", "..");
  const configPath = path.resolve(repoRoot, "configs", "plugin", "napcat-adapter.yaml");
  const secretsPath = path.resolve(repoRoot, "configs", "secrets.yaml");

  let config = { ...DEFAULT_CONFIG };
  if (fs.existsSync(configPath)) {
    const rawConfig = fs.readFileSync(configPath, "utf8");
    const parsed = yaml.parse(rawConfig) || {};
    config = mergeConfig(DEFAULT_CONFIG, parsed);
  }

  config.transport.access_token = resolveAccessToken(config.transport, secretsPath);
  config.transport.path = normalizePath(config.transport.path);
  config.ingress.blocked_user_ids = (config.ingress.blocked_user_ids || []).map(String);
  config.ingress.blocked_group_ids = (config.ingress.blocked_group_ids || []).map(String);
  config.ingress.wake_words = (config.ingress.wake_words || []).filter(Boolean);
  config.main_user.qq = String(config.main_user.qq || "").trim();
  config.memory.root_dir = String(config.memory.root_dir || "data/memory/adapters/napcat").trim();
  config.memory.max_scene_records = Number(config.memory.max_scene_records || 80);
  config.routing.session_partition.private = String(config.routing.session_partition.private || "by_source").trim();
  config.routing.session_partition.group = String(config.routing.session_partition.group || "by_source").trim();
  config.runtime.nickname_cache_ttl_ms = Number(config.runtime.nickname_cache_ttl_ms || 300000);

  return {
    config,
    configPath,
  };
}

module.exports = {
  DEFAULT_CONFIG,
  loadNapcatConfig,
};
