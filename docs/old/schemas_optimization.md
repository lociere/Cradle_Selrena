# Schemas 架构优化总结

**日期**: 2024  
**版本**: 2.0.0 (DDD 分层架构)  
**状态**: ✅ 完成

---

## 📊 优化概览

### 核心决策
- **完全迁移**: 不保留旧架构（soul/vessel）的任何文件或兼容性
- **清晰分层**: 按照 DDD 架构规范组织 schemas 文件夹
- **提示词系统**: 创建完整的提示词管理系统，支持动态渲染

### 优化范围
| 类别 | 旧架构 | 新架构 | 状态 |
|------|--------|--------|------|
| Schema 文件 | soul.py, events.py, payloads.py | domain.py, system.py | ✅ 完成 |
| 提示词管理 | 旧的 persona/prompts | schemas/prompts | ✅ 完成 |
| 配置文件 | 分散在多处 | configs/persona/prompts | ✅ 完成 |
| 人设提示词 | 硬编码或分散 | 模板化、可配置 | ✅ 完成 |

---

## 🗑️ 已删除的旧架构内容

### 文件（4 个）
```
❌ cradle-selrena-core/src/cradle_selrena_core/schemas/configs/soul.py (已重命名为 domain.py)
❌ cradle-selrena-core/src/cradle_selrena_core/schemas/events.py
❌ cradle-selrena-core/src/cradle_selrena_core/schemas/payloads.py
❌ cradle-selrena-core/src/cradle_selrena_core/persona/prompts/ (整个目录)
```

### 目录结构
```
❌ schemas/
   ├── events.py         # 已删除（无实际内容）
   ├── payloads.py       # 已删除（无实际内容）
   └── configs/
       └── soul.py       # 已重命名为 domain.py
```

---

## ✅ 新建的新架构内容

### Schemas 目录结构
```
✅ schemas/
   ├── __init__.py
   ├── configs/
   │   ├── __init__.py
   │   ├── system.py      # 系统配置 Schema
   │   └── domain.py      # Domain 层配置 Schema（原 soul.py）
   └── prompts/
       ├── __init__.py
       └── prompt_manager.py  # 提示词管理器
```

### 提示词模板（2 个）
```
✅ configs/persona/prompts/
   ├── system_prompt.md              # 静态提示词（月见人设）
   └── system_prompt.template.md     # Jinja2 动态模板
```

### PromptManager 类
```python
✅ PromptManager
   ├── load_prompt()      # 加载静态提示词
   ├── render_prompt()    # 渲染动态模板
   └── get_system_prompt() # 获取完整系统提示词
```

---

## 📝 人设提示词迁移

### 旧提示词内容
```markdown
name: 月见 (Selrena)
role: 可爱少女
personality: 理性主导的腹黑少女，表面开朗正经实则思维跳脱
appearance: 银色长发，17-18 岁少女
character_core: 5 个性格核心特征
likes: 舒缓安静事物，对新鲜事物有好奇心
background: 年龄不详的神秘少女
dialogue_style: 轻松、戏谑、跳跃性
emotion_control: 语音情感标签控制
taboos: 3 大禁忌（禁止动作描述、AI 自称、服务语气）
```

### 新提示词结构

#### 1. 静态提示词 (`system_prompt.md`)
- 完整的人设描述
- 固定的性格特征
- 对话风格和禁忌
- 情感控制规则

#### 2. 动态模板 (`system_prompt.template.md`)
- 使用 Jinja2 模板引擎
- 支持动态变量：
  - `{{ persona_name }}`: 人格名称
  - `{{ persona_role }}`: 角色
  - `{{ memory_summary }}`: 记忆摘要
  - `{{ user_profile }}`: 用户画像
  - `{{ conversation_history }}`: 对话历史

### 迁移对比

| 特性 | 旧架构 | 新架构 |
|------|--------|--------|
| 提示词位置 | 硬编码或分散 | 统一的 configs/persona/prompts |
| 模板引擎 | 无 | Jinja2 |
| 动态渲染 | ❌ | ✅ |
| 上下文支持 | ❌ | ✅ (记忆、用户、对话历史) |
| 可配置性 | 低 | 高（通过配置文件） |

---

## 🏗️ Schema 文件重命名

### soul.py → domain.py

**原因**:
- 符合 DDD 架构规范（Domain 层）
- 避免使用模糊的"soul"概念
- 与配置目录结构一致（configs/domain/）

**兼容性处理**:
```python
# domain.py 末尾保留别名
SoulConfig = DomainConfig  # 向后兼容
```

**影响范围**:
- ✅ 导入路径：`from schemas.configs import DomainConfig`
- ✅ 配置文件：`configs/domain/core.yaml`
- ✅ 向后兼容：`SoulConfig` 别名保留

---

## 🔧 PromptManager 使用示例

### 基础使用

```python
from cradle_selrena_core.schemas.prompts import PromptManager, PromptContext

# 创建管理器
manager = PromptManager()

# 加载静态提示词
prompt = manager.load_prompt("system_prompt")

# 渲染动态模板
context = PromptContext(
    persona_name="月见",
    persona_role="可爱少女",
    memory_summary="用户最近对 AI 技术很感兴趣",
    user_profile="用户名：测试用户"
)
rendered = manager.render_prompt("system_prompt", context=context)
```

### 高级使用

```python
# 获取完整的系统提示词（包含上下文）
system_prompt = manager.get_system_prompt(
    persona_config={
        "name": "月见",
        "identity": {"role": "可爱少女"}
    },
    memory_summary="用户询问了关于提示词管理的问题",
    user_profile="活跃用户",
    conversation_history="..."
)
```

### 与配置集成

```python
from cradle_selrena_core.schemas.configs import DomainConfig

# 加载配置
config = DomainConfig()

# 配置中包含提示词模板路径
print(config.persona.prompt_template)
# 输出：configs/persona/prompts/system_prompt.template.md
```

---

## 📋 配置文件更新

### configs/domain/core.yaml

添加了提示词模板路径配置：

```yaml
persona:
  name: "Selrena"
  # ... 其他配置
  prompt_template: "configs/persona/prompts/system_prompt.template.md"
```

### Schema 模型更新

```python
class PersonaConfig(BaseModel):
    name: str = "Selrena"
    # ... 其他字段
    prompt_template: str = "configs/persona/prompts/system_prompt.template.md"
```

---

## 🎯 新架构特性

### 1. 模板化提示词
- 使用 Jinja2 模板引擎
- 支持动态变量替换
- 可配置模板路径

### 2. 上下文感知
- 支持记忆摘要
- 支持用户画像
- 支持对话历史

### 3. 灵活加载
- 静态提示词：直接加载 `.md` 文件
- 动态模板：渲染 `.template.md` 文件
- 智能回退：模板不存在时回退到静态版本

### 4. 路径智能检测
- 多路径策略（3 层回退）
- 适应不同运行环境
- 自动创建目录

---

## ✅ 验证清单

- [x] 删除旧的 events.py 和 payloads.py
- [x] 重命名 soul.py 为 domain.py
- [x] 创建 prompts 目录结构
- [x] 迁移人设提示词到新架构
- [x] 创建 PromptManager 类
- [x] 创建静态和动态提示词模板
- [x] 更新配置文件添加提示词路径
- [x] 更新 Schema 模型添加 prompt_template 字段
- [x] 测试提示词加载和渲染
- [x] 验证路径智能检测

---

## 📊 迁移统计

| 指标 | 数量 |
|------|------|
| 删除旧文件 | 4 个 |
| 重命名文件 | 1 个 |
| 新建目录 | 2 个 |
| 新建文件 | 4 个 |
| 更新 Schema | 2 个类 |
| 更新配置文件 | 1 个 |
| 提示词模板 | 2 个 |

---

## 🚀 下一步行动

### 立即可用
- ✅ PromptManager 已就绪，可以立即使用
- ✅ 提示词模板已创建（静态 + 动态）
- ✅ 配置文件已更新

### 后续优化（可选）
1. **扩展提示词模板**: 创建更多场景的提示词（如情感回复、知识问答等）
2. **提示词版本管理**: 支持多版本提示词切换
3. **提示词评估**: 添加提示词效果评估机制
4. **多语言支持**: 支持多语言提示词模板

---

## 🎉 总结

**优化状态**: ✅ 完成  
**架构状态**: ✅ 稳定  
**可用性**: ✅ 立即可用  

新的 Schemas 架构已完全就绪，旧的 soul/vessel 架构已彻底清理。提示词系统实现了模板化、动态化、可配置化。

**关键优势**:
- 🎯 架构清晰，符合 DDD 规范
- 📝 提示词模板化，支持动态渲染
- 🔧 高度可配置，通过配置文件管理
- 🚀 立即可用，测试验证通过

---

**维护者**: Cradle Selrena Team  
**许可证**: MIT
