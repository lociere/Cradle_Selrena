/**
 * 全局配置管理器
 * 全项目所有配置的唯一可信源
 * 负责配置的加载、校验、冻结、热重载
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

const logger = getLogger("config-manager");

/**
 * 全局配置管理器
 * 单例模式
 */
export class ConfigManager {
  private static _instance: ConfigManager | null = null;
  private _config: GlobalConfig | null = null;
  private _configDir: string = this.resolveConfigDir();
  private _isInitialized: boolean = false;
  private _isFrozen: boolean = false;

  private resolveConfigDir(): string {
    let dir = process.cwd();
    while (true) {
      const candidate = path.join(dir, "configs");
      if (fs.existsSync(candidate)) {
        return candidate;
      }
      const parent = path.dirname(dir);
      if (parent === dir) break;
      dir = parent;
    }
    return path.resolve(process.cwd(), "configs");
  }

  public static get instance(): ConfigManager {
    if (!ConfigManager._instance) {
      ConfigManager._instance = new ConfigManager();
    }
    return ConfigManager._instance;
  }

  private constructor() {}

  public async init(): Promise<void> {
    if (this._isInitialized) {
      logger.warn("配置管理器已初始化，跳过重复初始化");
      return;
    }

    logger.info("开始初始化配置管理器", { config_dir: this._configDir });

    if (!(await fs.pathExists(this._configDir))) {
      throw new CoreException(`配置目录不存在: ${this._configDir}`, ErrorCode.CONFIG_ERROR);
    }

    try {
      const appConfig = await this.loadYamlConfig<GlobalConfig["app"]>("general.yaml");
      const aiConfig = await this.loadYamlConfig<GlobalConfig["ai"]>(
        path.join("python-ai", "inference.yaml")
      );
      const personaConfig = await this.loadYamlConfig<GlobalConfig["ai"]["persona"]>(
        path.join("python-ai", "persona.yaml")
      );
      aiConfig.persona = personaConfig;

      const llmConfig = await this.loadYamlConfig<GlobalConfig["ai"]["llm"]>(
        path.join("python-ai", "llm.yaml")
      );

      if (llmConfig) {
        await this.injectLLMApiKeysFromSecrets(llmConfig as any);
      }
      aiConfig.llm = llmConfig;

      const ipcConfig = await this.loadYamlConfig<GlobalConfig["ipc"]>(
        path.join("kernel", "ipc.yaml")
      );
      const lifecycleConfig = await this.loadYamlConfig<GlobalConfig["lifecycle"]>(
        path.join("kernel", "lifecycle.yaml")
      );
      const memoryConfig = await this.loadYamlConfig<GlobalConfig["memory"]>(
        path.join("kernel", "memory.yaml")
      );
      const pluginConfig = await this.loadYamlConfig<GlobalConfig["plugin"]>(
        path.join("kernel", "plugin.yaml")
      );

      const rawConfig: GlobalConfig = {
        app: appConfig,
        ai: aiConfig,
        ipc: ipcConfig,
        lifecycle: lifecycleConfig,
        memory: memoryConfig,
        plugin: pluginConfig,
      };

      const validationResult = GlobalConfigSchema.safeParse(rawConfig);
      if (!validationResult.success) {
        const errorDetails = validationResult.error.issues
          .map((issue) => `${issue.path.join('.')}: ${issue.message}`)
          .join('; ');
        throw new CoreException(`配置校验失败: ${errorDetails}`, ErrorCode.CONFIG_ERROR);
      }

      this._config = validationResult.data;
      this._isInitialized = true;

      logger.info("配置管理器初始化完成", {
        app_name: this._config.app.app_name,
        app_version: this._config.app.app_version,
      });
    } catch (error) {
      logger.error("配置管理器初始化失败", { error: (error as Error).message });
      throw error;
    }
  }

  private async loadYamlConfig<T>(relativePath: string): Promise<T> {
    const filePath = path.join(this._configDir, relativePath);
    logger.debug("开始加载配置文件", { file_path: filePath });

    if (!(await fs.pathExists(filePath))) {
      throw new CoreException(`配置文件不存在: ${filePath}`, ErrorCode.CONFIG_ERROR);
    }

    try {
      const fileContent = await fs.readFile(filePath, "utf-8");
      const parsedConfig = yaml.parse(fileContent);
      logger.debug("配置文件加载成功", { file_path: filePath });
      return parsedConfig as T;
    } catch (error) {
      throw new CoreException(
        `配置文件解析失败: ${filePath}, 错误: ${(error as Error).message}`,
        ErrorCode.CONFIG_ERROR
      );
    }
  }

  private async loadJsonConfig<T>(relativePath: string): Promise<T> {
    const filePath = path.join(this._configDir, relativePath);
    logger.debug("开始加载JSON配置文件", { file_path: filePath });

    if (!(await fs.pathExists(filePath))) {
      throw new CoreException(`配置文件不存在: ${filePath}`, ErrorCode.CONFIG_ERROR);
    }

    try {
      const fileContent = await fs.readFile(filePath, "utf-8");
      const parsedConfig = JSON.parse(fileContent) as T;
      logger.debug("JSON配置文件加载成功", { file_path: filePath });
      return parsedConfig;
    } catch (error) {
      throw new CoreException(
        `JSON配置文件解析失败: ${filePath}, 错误: ${(error as Error).message}`,
        ErrorCode.CONFIG_ERROR
      );
    }
  }

  private async injectLLMApiKeysFromSecrets(llmConfig: {
    api_type?: string;
    api_key?: string;
    providers?: Record<string, { api_key?: string }>;
  }): Promise<void> {
    const secretsPath = path.join(this._configDir, "secret", "secrets.yaml");
    if (!(await fs.pathExists(secretsPath))) {
      return;
    }

    try {
      const secretsContent = await fs.readFile(secretsPath, "utf-8");
      const secrets = yaml.parse(secretsContent) as {
        providers?: Record<string, { api_key?: string }>;
      };

      const providerMap = secrets?.providers || {};

      if (!llmConfig.api_key) {
        const providerKey = String(llmConfig.api_type || "deepseek").toLowerCase();
        const provider = providerMap[providerKey];
        if (provider?.api_key) {
          llmConfig.api_key = provider.api_key;
          logger.info("已从 secrets.yaml 自动注入 LLM API Key", { provider: providerKey });
        }
      }

      if (llmConfig.providers) {
        for (const [providerName, providerConfig] of Object.entries(llmConfig.providers)) {
          if (providerConfig?.api_key) {
            continue;
          }
          const secretProvider = providerMap[String(providerName).toLowerCase()];
          if (secretProvider?.api_key) {
            providerConfig.api_key = secretProvider.api_key;
            logger.info("已从 secrets.yaml 自动注入多 Provider API Key", { provider: providerName });
          }
        }
      }
    } catch {
      // 忽略 secrets 解析错误，继续使用 llm.yaml 中配置
    }
  }

  public getConfig(): Readonly<GlobalConfig> {
    if (!this._isInitialized || !this._config) {
      throw new CoreException("配置管理器未初始化", ErrorCode.CONFIG_ERROR);
    }
    return Object.freeze(this._config);
  }

  public freezeCoreConfig(): void {
    if (this._isFrozen) {
      return;
    }
    if (!this._config) {
      throw new CoreException("配置未加载，无法冻结", ErrorCode.CONFIG_ERROR);
    }
    Object.freeze(this._config.ai);
    Object.freeze(this._config.ai.persona);
    Object.freeze(this._config.ai.inference);
    this._isFrozen = true;
    logger.info("核心配置已冻结，运行时不可修改");
  }

  public async reloadConfig(): Promise<void> {
    logger.info("开始重载配置文件");
    const oldConfig = this._config;
    this._isInitialized = false;
    this._isFrozen = false;

    try {
      await this.init();
      this.freezeCoreConfig();
      logger.info("配置重载完成");
    } catch (error) {
      this._config = oldConfig;
      this._isInitialized = true;
      this._isFrozen = true;
      logger.error("配置重载失败，已回滚到旧配置", { error: (error as Error).message });
      throw error;
    }
  }

  public async loadKnowledgeBaseConfig(): Promise<KnowledgeBaseConfig> {
    const relativePath = path.join("python-ai", "knowledge-base.json");
    const rawConfig = await this.loadJsonConfig<unknown>(relativePath);
    const parsed = KnowledgeBaseConfigSchema.safeParse(rawConfig);

    if (!parsed.success) {
      const detail = parsed.error.issues
        .map((issue) => `${issue.path.join(".")}: ${issue.message}`)
        .join("; ");
      throw new CoreException(`知识库配置校验失败: ${detail}`, ErrorCode.CONFIG_ERROR);
    }

    return parsed.data;
  }

  public async loadEnabledPlugins(): Promise<string[]> {
    try {
      const filePath = path.join(this._configDir, "plugin/enabled-plugins.yaml");
      const fileContent = await fs.readFile(filePath, "utf-8");
      const config = yaml.parse(fileContent);
      return Array.isArray(config.enabled_plugins) ? config.enabled_plugins : [];
    } catch (error) {
      logger.error("启用插件列表加载失败", { error: (error as Error).message });
      return [];
    }
  }
}
