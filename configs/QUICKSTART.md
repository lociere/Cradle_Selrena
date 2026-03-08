# 新配置系统快速入门

> 🎉 恭喜！新的 DDD 分层配置系统已准备就绪！

## 🚀 5 分钟快速开始

### 步骤 1: 检查配置文件（1 分钟）

配置文件已创建在 `configs/` 目录下：

```bash
# Windows PowerShell
cd configs
ls

# 应该看到以下文件：
# core/system.yaml
# domain/core.yaml
# inference/engines.yaml
# adapters/napcat.yaml
# environments/settings.yaml
```

### 步骤 2: 填写敏感信息（2 分钟）

编辑 `configs/secrets.yaml` 或创建 `.env` 文件：

```yaml
# configs/secrets.yaml
llm:
  remote_api_key: "sk-your-actual-api-key-here"

napcat:
  access_token: "your-actual-napcat-token-here"

azure:
  tts_key: "your-actual-azure-tts-key-here"
  tts_region: "eastasia"
```

或使用 `.env` 文件（推荐）：

```bash
# .env
NAPCAT_ACCESS_TOKEN=your-actual-token-here
REMOTE_LLM_API_KEY=sk-your-actual-api-key-here
AZURE_TTS_KEY=your-actual-tts-key-here
```

### 步骤 3: 验证配置（1 分钟）

```bash
cd cradle-selrena-core
python tests/test_config_loading.py
```

如果看到以下输出，说明配置系统工作正常：

```
============================================================
Cradle Selrena 配置系统测试
============================================================

✓ SystemSettings 创建成功
✓ DomainConfig 创建成功
✓ 默认值测试通过

============================================================
测试完成！
============================================================
```

## 📋 配置项快速参考

### Core 层 - 系统核心
```yaml
# configs/core/system.yaml
system:
  logging:
    level: "INFO"  # DEBUG, INFO, WARNING, ERROR
  timeouts:
    llm_request: 120  # LLM 请求超时（秒）
```

### Domain 层 - 人格与记忆
```yaml
# configs/domain/core.yaml
persona:
  name: "Selrena"
  identity:
    role: "AI 伴侣"
  emotions:
    enabled: true

memory:
  storage:
    type: "hybrid"
  short_term:
    max_messages: 50
```

### Inference 层 - LLM 引擎
```yaml
# configs/inference/engines.yaml
llm:
  default_engine: "local_qwen"
  engines:
    local_qwen:
      model_path: "assets/models/Qwen2.5-7B-Instruct-Q4_K_M.gguf"
      n_ctx: 4096
      n_threads: 8
```

### Adapters 层 - QQ 适配器
```yaml
# configs/adapters/napcat.yaml
napcat:
  enabled: false  # 改为 true 启用
  bot_qq: 1234567890
  wake_words: ["月见", "selrena", "Selrena"]
```

### Environments 层 - 环境配置
```yaml
# configs/environments/settings.yaml
development:
  debug: true
  logging:
    level: "DEBUG"

production:
  debug: false
  logging:
    level: "WARNING"
```

## 🔧 常用操作

### 切换环境

```bash
# 开发环境
$env:ENV="development"
python main.py

# 生产环境
$env:ENV="production"
python main.py
```

### 验证配置语法

```bash
python -c "
import yaml
from pathlib import Path

configs = [
    'configs/core/system.yaml',
    'configs/domain/core.yaml',
    'configs/inference/engines.yaml',
    'configs/adapters/napcat.yaml',
]

for config in configs:
    try:
        with open(config, 'r', encoding='utf-8') as f:
            yaml.safe_load(f)
        print(f'✓ {config} 语法正确')
    except Exception as e:
        print(f'✗ {config} 错误：{e}')
"
```

### 查看配置结构

```bash
# 查看配置目录树
tree configs /F
```

## 📚 深入学习

### 完整文档
- [配置系统总览](README.md) - 详细的配置说明
- [配置迁移指南](../cradle-selrena-core/docs/config_migration_guide.md) - 从旧架构迁移
- [重构完成报告](../CONFIG_REFACTOR_COMPLETE.md) - 完整的功能列表

### Schema 模型
- [SystemSettings](../cradle-selrena-core/src/cradle_selrena_core/schemas/configs/system.py)
- [DomainConfig](../cradle-selrena-core/src/cradle_selrena_core/schemas/configs/soul.py)

### 测试脚本
- [配置加载测试](../cradle-selrena-core/tests/test_config_loading.py)

## ❓ 常见问题

### Q: 配置文件在哪里？
A: 所有配置文件都在 `configs/` 目录下，按 DDD 分层组织。

### Q: 如何备份旧配置？
A: 
```bash
cp -r configs configs.backup
```

### Q: 配置不生效怎么办？
A: 
1. 检查 YAML 语法是否正确
2. 确认配置文件名称（去掉 `.example`）
3. 运行测试脚本验证
4. 查看日志输出

### Q: 如何为不同环境使用不同配置？
A: 使用 `configs/environments/` 目录下的环境特定配置，通过 `ENV` 环境变量切换。

### Q: 敏感信息泄露了怎么办？
A: 
1. 立即撤销泄露的密钥
2. 检查 `.gitignore` 是否包含 `secrets.yaml`
3. 使用 `.env` 文件管理敏感信息
4. 永远不要提交真实密钥到 Git

## 🎯 下一步

1. ✅ 复制配置模板
2. ✅ 填写敏感信息
3. ✅ 验证配置
4. 📝 根据实际需求调整配置项
5. 🚀 启动应用

---

**需要帮助？** 查看 [完整文档](README.md) 或 [迁移指南](../cradle-selrena-core/docs/config_migration_guide.md)

**架构版本**: 2.0.0 (DDD)  
**最后更新**: 2024
