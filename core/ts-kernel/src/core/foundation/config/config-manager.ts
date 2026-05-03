import process from 'node:process';
import fs from 'fs-extra';
import path from 'path';
import yaml from 'yaml';
import {
  CoreException,
  ErrorCode,
  KnowledgeBaseConfig,
  KnowledgeBaseConfigSchema,
} from '@cradle-selrena/protocol';
import { getLogger } from '../logger/logger';
import {
  ENABLED_EXTENSIONS_YAML_TEMPLATE,
  PERSONA_YAML_TEMPLATE,
  SECRETS_EXAMPLE_YAML_TEMPLATE,
  SYSTEM_YAML_TEMPLATE,
} from './config-defaults';
import { GlobalConfig, GlobalConfigSchema } from './config-schema';

const logger = getLogger('config-manager');

interface ExtensionConfigSchemaLike {
  safeParse(input: unknown): {
    success: boolean;
    data?: unknown;
  };
}

interface ProviderConfig {
  api_key?: string;
  models?: Record<string, string>;
}

interface LLMConfigLike {
  api_type?: string;
  api_key?: string;
  providers?: Record<string, ProviderConfig>;
}

export class ConfigManager {
  private static _instance: ConfigManager | null = null;

  private _config: GlobalConfig | null = null;
  private _configDir = this.resolveConfigDir();
  private _isInitialized = false;
  private _isFrozen = false;

  public static get instance(): ConfigManager {
    if (!ConfigManager._instance) {
      ConfigManager._instance = new ConfigManager();
    }
    return ConfigManager._instance;
  }

  private constructor() {}

  public async init(): Promise<void> {
    if (this._isInitialized) {
      logger.warn('配置管理器已初始化，跳过重复初始化');
      return;
    }

    logger.info('开始初始化配置管理器', { config_dir: this._configDir });

    if (!(await fs.pathExists(this._configDir))) {
      throw new CoreException(`配置目录不存在: ${this._configDir}`, ErrorCode.CONFIG_ERROR);
    }

    await this.generateDefaults();

    try {
      const systemData = await this.loadYaml('system.yaml');
      const personaData = await this.loadYaml('persona.yaml');

      if (personaData.llm && typeof personaData.llm === 'object') {
        await this.injectLLMApiKeysFromSecrets(personaData.llm as LLMConfigLike);
      }

      const result = GlobalConfigSchema.safeParse({
        system: systemData,
        persona: personaData,
      });

      if (!result.success) {
        const detail = result.error.issues
          .map((issue) => `${issue.path.join('.')}: ${issue.message}`)
          .join('; ');
        throw new CoreException(`配置校验失败: ${detail}`, ErrorCode.CONFIG_ERROR);
      }

      this._config = result.data;
      this._isInitialized = true;

      logger.info('配置管理器初始化完成', {
        app_name: this._config.system.app_name,
        app_version: this._config.system.app_version,
      });
    } catch (error) {
      logger.error('配置管理器初始化失败', {
        error: error instanceof Error ? error.message : String(error),
      });
      throw error;
    }
  }

  public getConfig(): Readonly<GlobalConfig> {
    if (!this._isInitialized || !this._config) {
      throw new CoreException('配置管理器未初始化', ErrorCode.CONFIG_ERROR);
    }
    return Object.freeze(this._config);
  }

  public freezeCoreConfig(): void {
    if (this._isFrozen) {
      return;
    }
    if (!this._config) {
      throw new CoreException('配置尚未加载，无法冻结', ErrorCode.CONFIG_ERROR);
    }

    Object.freeze(this._config.persona);
    Object.freeze(this._config.persona.persona);
    Object.freeze(this._config.persona.inference);
    this._isFrozen = true;

    logger.info('核心配置已冻结，运行时不再允许修改');
  }

  public async reloadConfig(): Promise<void> {
    logger.info('开始重载配置文件');
    const backup = this._config;
    const wasFrozen = this._isFrozen;

    this._config = null;
    this._isInitialized = false;
    this._isFrozen = false;

    try {
      await this.init();
      if (wasFrozen) {
        this.freezeCoreConfig();
      }
      logger.info('配置重载完成');
    } catch (error) {
      this._config = backup;
      this._isInitialized = backup !== null;
      this._isFrozen = wasFrozen;
      logger.error('配置重载失败，已回滚到旧配置', {
        error: error instanceof Error ? error.message : String(error),
      });
      throw error;
    }
  }

  public async loadKnowledgeBaseConfig(): Promise<KnowledgeBaseConfig> {
    const raw = await this.loadJson('knowledge-base.json');
    const parsed = KnowledgeBaseConfigSchema.safeParse(raw);

    if (!parsed.success) {
      const detail = parsed.error.issues
        .map((issue) => `${issue.path.join('.')}: ${issue.message}`)
        .join('; ');
      throw new CoreException(`知识库配置校验失败: ${detail}`, ErrorCode.CONFIG_ERROR);
    }

    return parsed.data;
  }

  public async loadEnabledExtensions(): Promise<string[]> {
    try {
      const filePath = path.join(this._configDir, 'active-extensions.yaml');
      const content = await fs.readFile(filePath, 'utf-8');
      const parsed = yaml.parse(content) as { enabled_extensions?: unknown } | null;
      return Array.isArray(parsed?.enabled_extensions)
        ? parsed.enabled_extensions.filter((item): item is string => typeof item === 'string')
        : [];
    } catch (error) {
      logger.error('启用扩展列表加载失败', {
        error: error instanceof Error ? error.message : String(error),
      });
      return [];
    }
  }

  public async generateDefaults(): Promise<void> {
    const targets: Array<{ relativePath: string; content: string }> = [
      { relativePath: 'system.yaml', content: SYSTEM_YAML_TEMPLATE },
      { relativePath: 'persona.yaml', content: PERSONA_YAML_TEMPLATE },
      {
        relativePath: path.join('secret', 'secrets.example.yaml'),
        content: SECRETS_EXAMPLE_YAML_TEMPLATE,
      },
      { relativePath: 'active-extensions.yaml', content: ENABLED_EXTENSIONS_YAML_TEMPLATE },
    ];

    for (const { relativePath, content } of targets) {
      const filePath = path.join(this._configDir, relativePath);
      await fs.ensureDir(path.dirname(filePath));

      if (await fs.pathExists(filePath)) {
        logger.debug('配置文件已存在，跳过生成', { file: relativePath });
        continue;
      }

      await fs.writeFile(filePath, content, 'utf-8');
      logger.info('已生成默认配置文件', { file: relativePath });
    }
  }

  public async generateExtensionDefaults(
    extensionId: string,
    schema: ExtensionConfigSchemaLike,
  ): Promise<boolean> {
    const filePath = path.join(this._configDir, 'extension', `${extensionId}.yaml`);
    await fs.ensureDir(path.dirname(filePath));

    if (await fs.pathExists(filePath)) {
      return false;
    }

    try {
      const result = schema.safeParse({});
      if (!result.success || result.data == null) {
        logger.warn('扩展默认配置生成失败，schema 可能包含必填字段', {
          extension_id: extensionId,
        });
        return false;
      }

      const header = [
        `# ${extensionId} extension config`,
        '# Auto-generated by ConfigManager.',
        '',
      ].join('\n');

      await fs.writeFile(filePath, header + yaml.stringify(result.data, { indent: 2 }), 'utf-8');
      logger.info('已为扩展生成默认配置', {
        extension_id: extensionId,
        file: filePath,
      });
      return true;
    } catch (error) {
      logger.warn('扩展默认配置生成失败', {
        extension_id: extensionId,
        error: error instanceof Error ? error.message : String(error),
      });
      return false;
    }
  }

  private resolveConfigDir(): string {
    let currentDir = process.cwd();

    while (true) {
      const candidate = path.join(currentDir, 'configs');
      if (fs.existsSync(candidate)) {
        return candidate;
      }

      const parentDir = path.dirname(currentDir);
      if (parentDir === currentDir) {
        break;
      }
      currentDir = parentDir;
    }

    return path.resolve(process.cwd(), 'configs');
  }

  private async loadYaml(relativePath: string): Promise<Record<string, unknown>> {
    const filePath = path.join(this._configDir, relativePath);
    logger.debug('加载 YAML 配置文件', { file_path: filePath });

    if (!(await fs.pathExists(filePath))) {
      throw new CoreException(`配置文件不存在: ${filePath}`, ErrorCode.CONFIG_ERROR);
    }

    try {
      const content = await fs.readFile(filePath, 'utf-8');
      return (yaml.parse(content) ?? {}) as Record<string, unknown>;
    } catch (error) {
      throw new CoreException(
        `配置文件解析失败: ${filePath}: ${error instanceof Error ? error.message : String(error)}`,
        ErrorCode.CONFIG_ERROR,
      );
    }
  }

  private async loadJson(relativePath: string): Promise<unknown> {
    const filePath = path.join(this._configDir, relativePath);
    logger.debug('加载 JSON 配置文件', { file_path: filePath });

    if (!(await fs.pathExists(filePath))) {
      throw new CoreException(`配置文件不存在: ${filePath}`, ErrorCode.CONFIG_ERROR);
    }

    try {
      const content = await fs.readFile(filePath, 'utf-8');
      return JSON.parse(content);
    } catch (error) {
      throw new CoreException(
        `JSON 配置文件解析失败: ${filePath}: ${error instanceof Error ? error.message : String(error)}`,
        ErrorCode.CONFIG_ERROR,
      );
    }
  }

  private async injectLLMApiKeysFromSecrets(llmConfig: LLMConfigLike): Promise<void> {
    const secretsPath = path.join(this._configDir, 'secret', 'secrets.yaml');
    if (!(await fs.pathExists(secretsPath))) {
      return;
    }

    try {
      const content = await fs.readFile(secretsPath, 'utf-8');
      const secrets = yaml.parse(content) as { providers?: Record<string, ProviderConfig> } | null;
      const providers = secrets?.providers ?? {};

      if (!llmConfig.api_key) {
        const providerName = String(llmConfig.api_type ?? 'deepseek').toLowerCase();
        const provider = providers[providerName];
        if (provider?.api_key) {
          llmConfig.api_key = provider.api_key;
          logger.info('已从 secrets.yaml 注入默认 LLM API Key', { provider: providerName });
        }
      }

      if (!llmConfig.providers) {
        return;
      }

      for (const [providerName, providerConfig] of Object.entries(llmConfig.providers)) {
        if (providerConfig.api_key) {
          continue;
        }

        const secret = providers[providerName.toLowerCase()];
        if (secret?.api_key) {
          providerConfig.api_key = secret.api_key;
          logger.info('已注入 provider API Key', { provider: providerName });
        }
      }
    } catch (error) {
      logger.warn('读取 secrets.yaml 失败，继续使用显式配置', {
        error: error instanceof Error ? error.message : String(error),
      });
    }
  }
}