# 配置系统迁移指南

## 概述

本文档说明如何从旧架构的 `soul/vessel` 配置体系迁移到新的 DDD 分层配置体系。

## 架构对比

### 旧架构（已废弃）
```
configs/
├── soul/
│   ├── persona.yaml
│   ├── llm.yaml
│   └── memory.yaml
├── vessel/
│   ├── perception.yaml
│   ├── presentation.yaml
│   └── napcat.yaml
├── settings.yaml
└── secrets.yaml
```

### 新架构（DDD 分层）
```
configs/
├── core/                    # Core 层：系统核心配置
│   └── system.yaml
├── domain/                  # Domain 层：业务逻辑配置
│   ├── core.yaml           # 人格、记忆、决策
│   └── emotions.json       # 情感模型
├── inference/              # Inference 层：推理引擎配置
│   ├── engines.yaml        # LLM 引擎池
│   └── models.yaml         # 模型管理
├── adapters/               # Adapters 层：外部适配器
│   ├── napcat.yaml         # QQ 适配器
│   └── discord.yaml        # （预留）
├── environments/           # 环境分层配置
│   ├── settings.yaml       # 通用设置
│   ├── development.yaml    # 开发环境
│   └── production.yaml     # 生产环境
├── secrets.yaml            # 敏感信息（应加入 .gitignore）
└── secrets.example.yaml    # 敏感信息模板
```

## 迁移步骤

### 1. 备份旧配置
```bash
cp -r configs configs.legacy
```

### 2. 创建新配置目录
```bash
mkdir -p configs/{core,domain,inference,adapters,environments}
```

### 3. 迁移人格配置

**旧配置** (`configs/soul/persona.yaml`):
```yaml
persona:
  name: "月见"
  role: "伴侣"
  # ...
```

**新配置** (`configs/domain/core.yaml`):
```yaml
persona:
  name: "Selrena"
  version: "2.0"
  identity:
    role: "AI 伴侣"
    traits:
      - "温柔"
      - "聪慧"
  language:
    style: "亲切自然"
    formality: "casual"
  emotions:
    enabled: true
    model: "configs/persona/emotions.json"
  voice:
    provider: "azure_tts"
    voice_id: "zh-CN-XiaoxiaoNeural"
```

### 4. 迁移记忆配置

**旧配置** (`configs/soul/memory.yaml`):
```yaml
memory:
  enabled: true
  model_path: "moka-ai/m3e-small"
  short_term_window: 20
```

**新配置** (`configs/domain/core.yaml`):
```yaml
memory:
  storage:
    type: "hybrid"
    base_path: "data/selrena/memory"
  short_term:
    enabled: true
    max_messages: 50
    ttl_hours: 24
  long_term:
    enabled: true
    consolidation_threshold: 10
    embedding_model: "m3e-small"
  knowledge:
    enabled: true
    base_path: "data/knowledge"
    retrieval_top_k: 5
```

### 5. 迁移 LLM 配置

**旧配置** (`configs/soul/llm.yaml`):
```yaml
strategy:
  routing_mode: "split_tasks"
  core_provider: "local_embedded"
providers:
  local_embedded:
    provider: "openai"
    local_model_path: "assets/models/Qwen.gguf"
```

**新配置** (`configs/inference/engines.yaml`):
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
```

### 6. 迁移 NapCat 配置

**旧配置** (`configs/vessel/napcat.yaml`):
```yaml
napcat:
  enable: false
  account: 1234567890
  token: "your-token"
  wake_words: ["月见", "selrena"]
```

**新配置** (`configs/adapters/napcat.yaml`):
```yaml
napcat:
  enabled: false
  connection:
    type: "websocket"
    ws_url: "ws://localhost:8080/ws"
  bot_qq: 1234567890
  wake_words: ["月见", "selrena", "Selrena", "Lunaris", "/chat"]
  message:
    filter:
      ignore_self: true
    preprocessing:
      emoji:
        convert_to_text: true
  rate_limit:
    enabled: true
    max_messages_per_minute: 20
```

### 7. 迁移系统设置

**旧配置** (`configs/settings.yaml`):
```yaml
app:
  version: "0.1.0"
  debug: false
  log_level: "INFO"
```

**新配置** (`configs/core/system.yaml`):
```yaml
system:
  name: "Cradle Selrena"
  version: "2.0.0"
  logging:
    level: "INFO"
    format: "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    file:
      enabled: true
      path: "logs/selrena.log"
      max_size_mb: 50
  timeouts:
    llm_request: 120
    api_call: 30
  retry:
    max_attempts: 3
    base_delay: 1.0
```

### 8. 配置环境分层

**开发环境** (`configs/environments/development.yaml`):
```yaml
development:
  debug: true
  logging:
    level: "DEBUG"
  inference:
    llm:
      n_threads: 4
      n_ctx: 2048
  hot_reload:
    enabled: true
```

**生产环境** (`configs/environments/production.yaml`):
```yaml
production:
  debug: false
  logging:
    level: "WARNING"
  inference:
    llm:
      n_threads: 16
      n_ctx: 8192
      n_gpu_layers: 35
  monitoring:
    enabled: true
    metrics_port: 9090
  backup:
    enabled: true
    interval_hours: 6
```

## Schema 模型更新

### 旧 Schema (`schemas/configs/soul.py`)
```python
class SoulConfig(BaseModel):
    llm: LLMConfig
    persona: PersonaConfig
    memory: MemoryConfig
```

### 新 Schema (`schemas/configs/soul.py`)
```python
class DomainConfig(BaseModel):
    persona: PersonaConfig
    memory: MemoryConfig
    decision: DecisionConfig
```

### 新 Schema (`schemas/configs/system.py`)
```python
class SystemSettings(BaseModel):
    core: SystemCoreConfig
    adapters: AdapterConfig
    inference: InferenceConfig
    domain: DomainConfig
```

## 代码适配

### 配置加载器更新

**旧代码**:
```python
from cradle_selrena_core.schemas.configs import SoulConfig

config = SoulConfig.from_yaml("configs/soul/persona.yaml")
persona = config.persona
```

**新代码**:
```python
from cradle_selrena_core.schemas.configs import DomainConfig, SystemSettings

# 加载领域配置
domain_config = DomainConfig.from_yaml("configs/domain/core.yaml")
persona = domain_config.persona

# 或加载完整系统配置
system_config = SystemSettings.from_yaml("configs/system.yaml")
persona = system_config.domain.persona
```

## 环境变量

### 敏感信息管理

**推荐使用 `.env` 文件**:
```bash
# .env
NAPCAT_ACCESS_TOKEN=your-token-here
REMOTE_LLM_API_KEY=your-api-key-here
AZURE_TTS_KEY=your-tts-key-here
```

**在代码中读取**:
```python
import os
from dotenv import load_dotenv

load_dotenv()

napcat_token = os.getenv("NAPCAT_ACCESS_TOKEN")
llm_api_key = os.getenv("REMOTE_LLM_API_KEY")
```

## 验证迁移

### 1. 检查配置文件语法
```bash
python scripts/validate_configs.py
```

### 2. 运行导入测试
```bash
cd cradle-selrena-core
python -c "from cradle_selrena_core.schemas.configs import SystemSettings, DomainConfig; print('✓ Schema 导入成功')"
```

### 3. 加载配置测试
```bash
python -c "
from cradle_selrena_core.configs.loader import load_config
config = load_config('configs/domain/core.yaml')
print('✓ 配置加载成功')
print(f'人格名称：{config.persona.name}')
"
```

## 回滚方案

如果迁移后遇到问题，可以快速回滚到旧配置：

```bash
# 备份新配置
mv configs configs.new

# 恢复旧配置
mv configs.legacy configs

# 重启应用
python main.py
```

## 常见问题

### Q1: 旧配置文件还能用吗？
A: 不推荐。旧配置文件虽然可以通过兼容层加载，但会失去新架构的许多特性（如环境分层、引擎池管理等）。

### Q2: 需要同时保留新旧配置吗？
A: 不需要。迁移完成后，旧配置可以删除或归档。建议保留 `configs.legacy` 目录作为参考。

### Q3: 敏感信息如何处理？
A: 敏感信息应放入 `configs/secrets.yaml`（不提交到 Git），或使用 `.env` 文件通过环境变量管理。

### Q4: 如何为不同环境使用不同配置？
A: 使用 `configs/environments/` 目录下的环境特定配置文件。应用启动时根据 `ENV` 环境变量自动加载对应配置。

```bash
# 开发环境
ENV=development python main.py

# 生产环境
ENV=production python main.py
```

## 下一步

迁移完成后，建议：

1. **验证所有功能**：测试人格、记忆、推理、适配器等模块
2. **性能调优**：根据生产环境配置优化推理性能
3. **监控告警**：配置生产环境的监控和告警规则
4. **文档更新**：更新用户手册和开发文档中的配置相关章节

## 参考文档

- [架构设计全维度解析](docs/architecture/架构设计全维度解析：打造零妥协完美架构.md)
- [Python 结构优化文档](cradle-selrena-core/docs/python_structure_optimization.md)
- [配置 Schema 参考](cradle-selrena-core/src/cradle_selrena_core/schemas/configs/)
