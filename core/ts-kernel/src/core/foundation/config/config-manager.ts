/**
 * 全局配置管理器
 *
 * 全项目所有配置的唯一可信源。
 * 负责配置的加载、校验、冻结、热重载以及默认配置生成。
 *
 * 配置文件布局（configs/ 目录下）：
 *   system.yaml        → config.system   系统级（端口 / IPC / 日志 / 生命周期 / 插件）
 *   persona.yaml       → config.persona  角色人格与 AI 层（人格 / 推理 / LLM）
 *   secret/secrets.yaml                  敏感凭据（API Key）
 *   active-plugins.yaml                  启用的插件列表
 *   plugin/{id}.yaml                     各插件私有配置
 *   knowledge-base.json                  知识库条目
 */
import fs from "fs-extra";
import path from "path";
import yaml from "yaml";
import { GlobalConfig, GlobalConfigSchema } from "./config-schema";
import { getLogger } from "../logger/logger";
import {
  CoreException,
  ErrorCode,
  KnowledgeBaseConfig,
  KnowledgeBaseConfigSchema,
} from "@cradle-selrena/protocol";
import {
  SYSTEM_YAML_TEMPLATE,
  PERSONA_YAML_TEMPLATE,
  SECRETS_EXAMPLE_YAML_TEMPLATE,
  ENABLED_PLUGINS_YAML_TEMPLATE,
} from "./config-defaults";

const logger = getLogger("config-manager");

/**
 * 全局配置管理器（单例）
 */
export class ConfigManager {
  private static _instance: ConfigManager | null = null;
  private _config: GlobalConfig | null = null;
  private _configDir: string = this.resolveConfigDir();
  private _isInitialized: boolean = false;
  private _isFrozen: boolean = false;

  // ── 单例 ─────────────────────────────────────────────────

  public static get instance(): ConfigManager {
    if (!ConfigManager._instance) {
      ConfigManager._instance = new ConfigManager();
    }
    return ConfigManager._instance;
  }

  private constructor() {}

  // ── 初始化 ───────────────────────────────────────────────

  /**
   * 加载并校验全局配置。
   * 加载顺序：system.yaml → persona.yaml，合并后通过 Zod Schema 校验。
   * 缺失的配置文件自动从模板生成；缺失的配置项由 Zod default() 自动填充。
   */
  public async init(): Promise<void> {
    if (this._isInitialized) {
      logger.warn("配置管理器已初始化，跳过重复初始化");
      return;
    }

    logger.info("开始初始化配置管理器", { config_dir: this._configDir });

    if (!(await fs.pathExists(this._configDir))) {
      throw new CoreException(`配置目录不存在: ${this._configDir}`, ErrorCode.CONFIG_ERROR);
    }

    // 缺失的配置文件自动从模板生成（仅生成缺失文件，不覆盖已有文件）
    await this.generateDefaults();

    try {
      // 加载两个配置域
      const systemData = await this.loadYaml("system.yaml");
      const personaData = await this.loadYaml("persona.yaml");

      // 从 secrets.yaml 注入 LLM API Key
      if (personaData?.llm) {
        await this.injectLLMApiKeysFromSecrets(personaData.llm);
      }

      const rawConfig = {
        system: systemData,
        persona: personaData,
      };

      // Zod parse（非 safeParse）：缺失字段由 .default() 自动填充，多余字段被裁剪
      const result = GlobalConfigSchema.safeParse(rawConfig);
      if (!result.success) {
        const detail = result.error.issues
          .map((i) => `${i.path.join(".")}: ${i.message}`)
          .join("; ");
        throw new CoreException(`配置校验失败: ${detail}`, ErrorCode.CONFIG_ERROR);
      }

      this._config = result.data;
      this._isInitialized = true;

      logger.info("配置管理器初始化完成", {
        app_name: this._config.system.app_name,
        app_version: this._config.system.app_version,
      });
    } catch (error) {
      logger.error("配置管理器初始化失败", { error: (error as Error).message });
      throw error;
    }
  }

  // ── 访问 ─────────────────────────────────────────────────

  public getConfig(): Readonly<GlobalConfig> {
    if (!this._isInitialized || !this._config) {
      throw new CoreException("配置管理器未初始化", ErrorCode.CONFIG_ERROR);
    }
    return Object.freeze(this._config);
  }

  // ── 冻结 ─────────────────────────────────────────────────

  public freezeCoreConfig(): void {
    if (this._isFrozen) return;
    if (!this._config) {
      throw new CoreException("配置未加载，无法冻结", ErrorCode.CONFIG_ERROR);
    }
    Object.freeze(this._config.persona);
      Object.freeze(this._config.persona.persona);
      Object.freeze(this._config.persona.inference);
    this._isFrozen = true;
    logger.info("核心配置已冻结，运行时不可修改");
  }

  // ── 热重载 ───────────────────────────────────────────────

  public async reloadConfig(): Promise<void> {
    logger.info("开始重载配置文件");
    const backup = this._config;
    this._isInitialized = false;
    this._isFrozen = false;

    try {
      await this.init();
      this.freezeCoreConfig();
      logger.info("配置重载完成");
    } catch (error) {
      this._config = backup;
      this._isInitialized = true;
      this._isFrozen = true;
      logger.error("配置重载失败，已回滚到旧配置", { error: (error as Error).message });
      throw error;
    }
  }

  // ── 知识库（独立加载） ───────────────────────────────────

  public async loadKnowledgeBaseConfig(): Promise<KnowledgeBaseConfig> {
    const raw = await this.loadJson("knowledge-base.json");
    const parsed = KnowledgeBaseConfigSchema.safeParse(raw);
    if (!parsed.success) {
      const detail = parsed.error.issues
        .map((i) => `${i.path.join(".")}: ${i.message}`)
        .join("; ");
      throw new CoreException(`知识库配置校验失败: ${detail}`, ErrorCode.CONFIG_ERROR);
    }
    return parsed.data;
  }

  // ── 插件列表 ─────────────────────────────────────────────

  public async loadEnabledPlugins(): Promise<string[]> {
    try {
      const filePath = path.join(this._configDir, "active-plugins.yaml");
      const content = await fs.readFile(filePath, "utf-8");
      const config = yaml.parse(content);
      return Array.isArray(config?.enabled_plugins) ? config.enabled_plugins : [];
    } catch (error) {
      logger.error("启用插件列表加载失败", { error: (error as Error).message });
      return [];
    }
  }

  // ── 默认配置生成 ─────────────────────────────────────────

  /**
   * 生成全局默认配置文件。
   * 已存在的文件不会被覆盖，仅写入缺失的文件。
   */
  public async generateDefaults(): Promise<void> {
    const targets: { relativePath: string; content: string }[] = [
      { relativePath: "system.yaml", content: SYSTEM_YAML_TEMPLATE },
      { relativePath: "persona.yaml", content: PERSONA_YAML_TEMPLATE },
      { relativePath: path.join("secret", "secrets.example.yaml"), content: SECRETS_EXAMPLE_YAML_TEMPLATE },
      { relativePath: "active-plugins.yaml", content: ENABLED_PLUGINS_YAML_TEMPLATE },
    ];

    for (const { relativePath, content } of targets) {
      const target = path.join(this._configDir, relativePath);
      await fs.ensureDir(path.dirname(target));
      if (await fs.pathExists(target)) {
        logger.debug("配置文件已存在，跳过生成", { file: relativePath });
        continue;
      }
      await fs.writeFile(target, content, "utf-8");
      logger.info("已生成默认配置文件", { file: relativePath });
    }
  }

  /**
   * 为插件生成默认配置文件。
   * 根据插件提供的 configSchema 自动导出默认值。
   * 已存在的配置文件不会被覆盖。
   *
   * @returns true 表示生成了新文件，false 表示文件已存在
   */
  public async generatePluginDefaults(
    pluginId: string,
    schema: { safeParse(input: unknown): { success: boolean; data?: unknown } },
  ): Promise<boolean> {
    const target = path.join(this._configDir, "plugin", `${pluginId}.yaml`);
    await fs.ensureDir(path.dirname(target));
    if (await fs.pathExists(target)) return false;

    try {
      const result = schema.safeParse({});
      if (!result.success || result.data == null) {
        logger.warn("插件默认配置生成失败（schema 存在必填字段）", { plugin_id: pluginId });
        return false;
      }
      const header = `# ${pluginId} 插件配置\n# 本文件由系统自动生成，请根据需要修改各配置项\n\n`;
      await fs.writeFile(target, header + yaml.stringify(result.data, { indent: 2 }), "utf-8");
      logger.info("已为插件生成默认配置", { plugin_id: pluginId, file: target });
      return true;
    } catch (error) {
      logger.warn("插件默认配置生成失败（schema 可能存在必填字段）", {
        plugin_id: pluginId,
        error: (error as Error).message,
      });
      return false;
    }
  }

  // ── 内部工具 ─────────────────────────────────────────────

  private resolveConfigDir(): string {
    let dir = process.cwd();
    while (true) {
      const candidate = path.join(dir, "configs");
      if (fs.existsSync(candidate)) return candidate;
      const parent = path.dirname(dir);
      if (parent === dir) break;
      dir = parent;
    }
    return path.resolve(process.cwd(), "configs");
  }

  private async loadYaml(relativePath: string): Promise<Record<string, unknown>> {
    const filePath = path.join(this._configDir, relativePath);
    logger.debug("加载配置文件", { file_path: filePath });

    if (!(await fs.pathExists(filePath))) {
      throw new CoreException(`配置文件不存在: ${filePath}`, ErrorCode.CONFIG_ERROR);
    }
    try {
      const content = await fs.readFile(filePath, "utf-8");
      return (yaml.parse(content) ?? {}) as Record<string, unknown>;
    } catch (error) {
      throw new CoreException(
        `配置文件解析失败: ${filePath}: ${(error as Error).message}`,
        ErrorCode.CONFIG_ERROR,
      );
    }
  }

  private async loadJson(relativePath: string): Promise<unknown> {
    const filePath = path.join(this._configDir, relativePath);
    logger.debug("加载 JSON 配置文件", { file_path: filePath });

    if (!(await fs.pathExists(filePath))) {
      throw new CoreException(`配置文件不存在: ${filePath}`, ErrorCode.CONFIG_ERROR);
    }
    try {
      const content = await fs.readFile(filePath, "utf-8");
      return JSON.parse(content);
    } catch (error) {
      throw new CoreException(
        `JSON 配置文件解析失败: ${filePath}: ${(error as Error).message}`,
        ErrorCode.CONFIG_ERROR,
      );
    }
  }

  private async injectLLMApiKeysFromSecrets(llmConfig: {
    api_type?: string;
    api_key?: string;
    providers?: Record<string, { api_key?: string; models: Record<string, string> }>;
  }): Promise<void> {
    const secretsPath = path.join(this._configDir, "secret", "secrets.yaml");
    if (!(await fs.pathExists(secretsPath))) return;

    try {
      const content = await fs.readFile(secretsPath, "utf-8");
      const secrets = yaml.parse(content) as {
        providers?: Record<string, { api_key?: string }>;
      };
      const providerMap = secrets?.providers ?? {};

      // 主 API Key 注入
      if (!llmConfig.api_key) {
        const key = String(llmConfig.api_type ?? "deepseek").toLowerCase();
        const provider = providerMap[key];
        if (provider?.api_key) {
          llmConfig.api_key = provider.api_key;
          logger.info("已从 secrets.yaml 自动注入 LLM API Key", { provider: key });
        }
      }

      // 多 Provider API Key 注入
      if (llmConfig.providers) {
        for (const [name, cfg] of Object.entries(llmConfig.providers)) {
          if (cfg?.api_key) continue;
          const secret = providerMap[name.toLowerCase()];
          if (secret?.api_key) {
            cfg.api_key = secret.api_key;
            logger.info("已注入多 Provider API Key", { provider: name });
          }
        }
      }
    } catch {
      // secrets 解析失败时静默降级，继续使用 persona.yaml 中的配置
    }
  }
}
