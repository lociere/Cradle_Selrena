# Cradle Selrena 配置系统总览

> **架构版本**: 2.0.0 (DDD 分层架构)  
> **最后更新**: 2024  
> **适用范围**: 整个项目（所有语言共享）

## 📁 配置目录结构

```
configs/
├── general.yaml               # 全局通用配置（项目名称/版本/路径等）
├── kernel/                    # 内核层配置（TS 内核专用）
│   ├── ipc.yaml
│   ├── lifecycle.yaml
│   ├── memory.yaml
│   └── plugin.yaml
├── renderer/                  # 渲染层配置（UI/窗口/Live2D 等）
│   ├── live2d.yaml
│   └── window.yaml
├── python-ai/                 # Python AI 层配置（人格/推理/LLM）
│   ├── persona.yaml
│   ├── inference.yaml
│   └── llm.yaml
├── plugin/                    # 插件系统配置（启用插件列表等）
│   └── enabled-plugins.yaml
├── plugin-samples/            # 插件示例配置（模板 / 参考用）
│   ├── core-scene.yaml
│   ├── live-platform.yaml
│   └── napcat-qq.yaml
└── secret/                    # 私密配置（不应提交到 Git）
    ├── secrets.yaml
    └── secrets.example.yaml
```

## 🏗️ 架构分层说明

### Core 层 (`configs/core/`)
**职责**: 系统级全局配置，不随业务逻辑变化

**包含**:
- 系统标识（名称、版本）
- 日志配置（级别、格式、输出目标）
- 全局超时设置
- 重试策略

**示例**:
```yaml
system:
  name: "Cradle Selrena"
  version: "2.0.0"
  logging:
    level: "INFO"
    format: "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
  timeouts:
    llm_request: 120
    api_call: 30
```

### Domain 层 (`configs/domain/`)
**职责**: 核心业务逻辑配置，定义 AI 的"灵魂"

**包含**:
- **人格 (Persona)**: 身份、性格、语言风格、情感系统、语音
  - 核心配置：`configs/domain/core.yaml`
  - 人设专属：`configs/domain/persona/`（提示词模板、情感模型）
- **记忆 (Memory)**: 存储策略、短期/长期记忆、知识管理
- **决策 (Decision)**: 思考模式、响应策略、行为参数

**示例**:
```yaml
persona:
  name: "Selrena"
  identity:
    role: "AI 伴侣"
    traits: ["温柔", "聪慧", "善解人意"]
  language:
    style: "亲切自然"
    formality: "casual"
  emotions:
    enabled: true
    model: "configs/domain/persona/emotions.json"

memory:
  storage:
    type: "hybrid"
    base_path: "data/selrena/memory"
  short_term:
    max_messages: 50
    ttl_hours: 24
  long_term:
    consolidation_threshold: 10
    embedding_model: "m3e-small"

decision:
  thinking_mode: "balanced"
  generation:
    temperature: 0.7
    top_p: 0.9
```

### Inference 层 (`configs/inference/`)
**职责**: 推理引擎与模型管理

**包含**:
- **LLM 引擎池**: 多个 LLM 引擎配置、负载均衡、健康检查
- **模型管理**: 缓存策略、自动下载、预热
- **嵌入模型**: 文本向量化模型配置
- **语音识别**: ASR 配置（可选）

**示例**:
```yaml
llm:
  default_engine: "local_qwen"
  engines:
    local_qwen:
      type: "llama_cpp"
      model_path: "assets/models/Qwen2.5-7B-Instruct-Q4_K_M.gguf"
      n_ctx: 4096
      n_threads: 8
      inference:
        temperature: 0.7
        top_p: 0.9
  pool:
    max_instances: 2
    recycling:
      idle_timeout_seconds: 300

embedding:
  default_model: "m3e-small"
  models:
    m3e-small:
      type: "sentence_transformers"
      model_path: "assets/models/m3e-small"
      device: "cpu"
```

### Adapters 层 (`configs/adapters/`)
**职责**: 外部平台适配与协议转换

**包含**:
- **NapCat (QQ)**: 连接配置、消息处理、群聊/私聊策略
- **其他平台**: Discord、Telegram 等（预留）
- **通用适配器**: 消息标准化、资源管理、事件总线

**示例**:
```yaml
napcat:
  enabled: false
  connection:
    type: "websocket"
    ws_url: "ws://localhost:8080/ws"
  bot_qq: 1234567890
  wake_words: ["月见", "selrena", "Selrena"]
  message:
    filter:
      ignore_self: true
    preprocessing:
      emoji:
        convert_to_text: true
      image:
        download: true
        caption_enabled: true
    rate_limit:
      enabled: true
      max_messages_per_minute: 20
```

### Platforms 层 (`configs/platforms/`)
**职责**: 平台特定的前端与交互配置

**包含**:
- **Live2D**: 模型加载、表情映射、动作触发
- **Audio Engine**: TTS 配置、语音播放、音效管理
- **其他平台**: Web UI、桌面应用等（预留）

**示例**:
```yaml
# live2d.yaml
live2d:
  enabled: true
  model:
    path: "assets/live2d/models/CurrentModel"
    scale: 1.0
    position:
      x: 0.5
      y: 0.5
  expression:
    mapping:
      happy: "exp_01.exp3.json"
      sad: "exp_02.exp3.json"
      angry: "exp_03.exp3.json"
  motion:
    idle: "idle_01.motion3.json"
    tap_head: "tap_head_01.motion3.json"

# audio.yaml
audio:
  tts:
    engine: "azure"
    voice: "zh-CN-XiaoxiaoNeural"
    rate: 1.0
    volume: 1.0
  playback:
    device: "default"
    buffer_size: 2048
```

### Environments 层 (`configs/environments/`)
**职责**: 环境特定的差异化配置

**包含**:
- **Development**: 调试模式、热重载、性能分析
- **Production**: 性能优化、监控、备份、安全
- **Testing**: 模拟数据、最小模型

**示例**:
```yaml
# development.yaml
development:
  debug: true
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
