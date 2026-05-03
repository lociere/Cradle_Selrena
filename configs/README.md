# Cradle Selrena 配置系统总览

> 架构基线：Unified Dual-Shell + AI Core + TS Kernel
> 适用范围：当前仓库 configs/ 目录

## 当前配置目录结构

```text
configs/
├── system.yaml                 # 系统级配置：日志、IPC、生命周期、扩展宿主、入站防护
├── persona.yaml                # AI Core 配置：人格、推理、LLM、嵌入、多模态、动作流
├── active-extensions.yaml      # 当前启用的 Adapter / Extension 清单
├── knowledge-base.json         # 知识库与人格素材
├── extension/
│   ├── napcat-adapter.yaml         # NapCat Adapter 配置
│   └── vtube-studio-adapter.yaml   # VTube Studio Adapter 配置
└── secret/
    ├── secrets.yaml
    └── secrets.example.yaml
```

当前仓库不再使用以下旧结构：

- general.yaml
- kernel/*.yaml 分拆目录
- renderer/*.yaml 分拆目录
- python-ai/*.yaml 分拆目录
- extension-samples/

## 配置职责划分

### system.yaml

负责系统运行时，不负责人格和推理语义。

主要内容：

- app_name / app_version
- log_level
- data_dir / log_dir / backup_dir
- ipc
- lifecycle
- extension
- ingress_gate

适合放在这里的内容：

- Kernel 如何启动和停止
- TS <-> Python IPC 参数
- 扩展宿主超时与默认权限
- 全局入站防护策略

不应放在这里的内容：

- 唤醒词
- 人格提示词
- 多模态路由策略
- 模型与推理参数

### persona.yaml

负责 AI Core 的人格与推理配置，是认知层的唯一主配置入口。

主要内容：

- persona
- inference.model
- inference.life_clock
- inference.memory
- inference.multimodal
- inference.action_stream
- inference.embedding
- llm

适合放在这里的内容：

- 月见人格锚点
- 推理温度、最大 token
- 生命时钟与记忆策略
- 多模态与动作流开关
- 嵌入模型和 LLM provider

### active-extensions.yaml

负责声明当前要启用哪些 Adapter / Extension。

当前典型内容：

- napcat-adapter
- vtube-studio-adapter

注意：

- Native Shell 不通过这里启用。
- renderer-ui 和 renderer-avatar 属于系统本体，不属于 active extensions。

### extension/*.yaml

负责每个插件自己的私有配置。

当前文件：

- napcat-adapter.yaml
- vtube-studio-adapter.yaml

规则：

- 文件名应与扩展 ID 保持一致。
- 旧扩展配置文件不应长期与新命名并存。
- 如果扩展 schema 允许 passthrough 字段，仍应优先保持配置命名清晰，不把历史垃圾无限保留。

### secret/

负责敏感凭据，不能把真实密钥散落到普通配置文件中。

规则：

- 优先通过环境变量或 secrets.yaml 注入。
- 普通配置文件中只保留 access_token_env 这类引用字段。
- 不应把真实 token 复制到多个文件中。

## 维护规则

### 1. 先改主配置，再改说明文档

配置体系调整时，必须同步更新：

- configs/README.md
- 对应 yaml 文件
- 读取这些配置的代码

### 2. 禁止继续扩散旧目录心智模型

后续文档和代码中，不要再写：

- configs/kernel/
- configs/python-ai/
- configs/renderer/

当前仓库已经统一为：

- system.yaml
- persona.yaml
- active-extensions.yaml
- extension/*.yaml

### 3. 配置文件名应服务于开发判断

命名应让人一眼知道配置属于哪一层：

- system：系统运行时
- persona：AI Core 人格与推理
- active-extensions：扩展装载面
- extension/napcat-adapter：具体扩展私有配置

### 4. Native Shell 不写进 extension 配置目录

桌面壳和头像壳不是插件，所以不要新增：

- configs/extension/renderer-ui.yaml
- configs/extension/renderer-avatar.yaml

这类配置如果未来需要，应进入 system.yaml 或专门的 shell 配置体系，而不是伪装成 extension。
  logging:
    level: "DEBUG"
  hot_reload:
    enabled: true
    watch_dirs: ["src", "configs"]
  dev_tools:
    profiling:
      enabled: true
    debug_api:
      enabled: true
      port: 8000

# production.yaml
production:
  debug: false
  logging:
    level: "WARNING"
  inference:
    llm:
      n_gpu_layers: 35
  monitoring:
    enabled: true
    metrics_port: 9090
  backup:
    enabled: true
    interval_hours: 6
```

## 🔐 敏感信息管理

### 使用 `.env` 文件（推荐）
```bash
# .env
NAPCAT_ACCESS_TOKEN=your-token-here
REMOTE_LLM_API_KEY=your-api-key-here
AZURE_TTS_KEY=your-tts-key-here
```

### 使用 `secrets.yaml`（兼容旧版）
```yaml
# configs/secrets.yaml（不提交到 Git）
llm:
  remote_api_key: "sk-..."
napcat:
  access_token: "..."
azure:
  tts_key: "..."
```

### 在代码中读取
```python
import os
from dotenv import load_dotenv

load_dotenv()

# 从环境变量读取
napcat_token = os.getenv("NAPCAT_ACCESS_TOKEN")
llm_api_key = os.getenv("REMOTE_LLM_API_KEY")
```

## 📊 配置 Schema 模型

所有配置文件都有对应的 Pydantic Schema 模型，位于：
`cradle-selrena/src/selrena/schemas/configs/`

### 核心 Schema

| Schema 文件 | 对应配置 | 根模型 |
|------------|---------|--------|
| `system.py` | `configs/core/system.yaml` | `SystemSettings` |
| `domain.py` | `configs/domain/core.yaml` | `DomainConfig` |
| （待扩展） | `configs/inference/engines.yaml` | `InferenceConfig` |
| （待扩展） | `configs/adapters/napcat.yaml` | `AdapterConfig` |

### 提示词管理

提示词管理代码位于：
`cradle-selrena/src/selrena/configs/prompts/`

**使用示例**：
```python
from selrena.configs.prompts import PromptManager, PromptContext

# 初始化提示词管理器（自动定位 configs/domain/persona/prompts）
pm = PromptManager()

# 加载静态提示词
prompt = pm.load_prompt("system_prompt")

# 渲染模板
context = PromptContext(
    persona_name="Selrena",
    persona_role="AI 伴侣",
    memory_summary="用户喜欢音乐和编程"
)
rendered = pm.render_prompt("system_prompt", context=context)

# 直接获取系统提示词
system_prompt = pm.get_system_prompt(
    persona_config={"name": "Selrena", "identity": {"role": "AI 伴侣"}},
    memory_summary="用户今天心情不错"
)
```

### 配置使用示例
```python
from selrena.schemas.configs import DomainConfig, SystemSettings
import yaml

# 加载领域配置
with open("configs/domain/core.yaml", "r", encoding="utf-8") as f:
    config_data = yaml.safe_load(f)
    domain_config = DomainConfig(**config_data)

# 访问配置
print(f"人格名称：{domain_config.persona.name}")
print(f"记忆存储类型：{domain_config.memory.storage.type}")
print(f"LLM 温度：{domain_config.decision.generation.temperature}")
```

## 🔄 配置加载流程

```
应用启动
    ↓
加载环境变量 (.env)
    ↓
加载基础配置 (configs/core/system.yaml)
    ↓
加载领域配置 (configs/domain/core.yaml)
    ↓
加载推理配置 (configs/inference/engines.yaml)
    ↓
加载适配器配置 (configs/adapters/*.yaml)
    ↓
根据环境叠加配置 (configs/environments/{ENV}.yaml)
    ↓
验证配置 (Pydantic 验证)
    ↓
初始化各模块
```

## 🛠️ 配置管理工具

### 验证配置语法
```bash
python scripts/validate_configs.py
```

### 生成配置模板
```bash
python scripts/generate_config_templates.py --output configs/
```

## 📝 最佳实践

### 1. 配置文件使用
- 当前配置文件均为实际可用版本（不带 `.example` 后缀）
- 如需自定义，建议先复制备份再修改
- 保持配置文件的版本控制（敏感信息除外）

### 2. 环境隔离
- 开发环境和生产环境使用不同的配置
- 敏感信息永远不要提交到 Git
- 使用 `.env.example` 模板提示需要的环境变量

### 3. 配置验证
- 所有配置必须通过 Pydantic 验证
- 在 CI/CD 流程中加入配置验证步骤
- 启动时进行配置完整性检查

### 4. 版本控制
- 配置文件（不含敏感信息）应提交到 Git
- 使用语义化版本号标记配置格式变更
- 在配置文件中添加版本注释

### 5. 文档化
- 每个配置项都应有清晰的注释
- 复杂配置提供使用示例
- 定期更新配置文档

## 🔗 相关文档

- [配置迁移指南](docs/config_migration_guide.md)
- [架构设计文档](docs/architecture/架构设计全维度解析：打造零妥协完美架构.md)
- [Python 结构优化](docs/python_structure_optimization.md)
- [Schema 模型参考](cradle-selrena/src/selrena/schemas/configs/)

## 📋 检查清单

在提交配置更改前，请确认：

- [ ] 配置文件已根据实际需求调整
- [ ] 敏感信息已移至 `secrets.yaml` 或 `.env`
- [ ] 配置文件通过 Pydantic 验证
- [ ] 更新了相关文档
- [ ] 测试了配置加载
- [ ] 确认环境分层配置正确

---

**维护者**: Cradle Selrena Team  
**许可证**: MIT
