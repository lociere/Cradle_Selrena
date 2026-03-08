# Platforms 层配置

平台特定的前端与交互配置。

## 设计原则

1. **平台隔离**: 每个平台独立配置文件，互不干扰
2. **语言特定**: 主要为 TypeScript/Node.js 前端服务
3. **可选启用**: 不需要的平台配置可以禁用或删除

## 文件结构

```
platforms/
├── live2d.yaml          # Live2D 模型渲染配置
├── audio.yaml           # TTS 与音频播放配置
├── web-ui.yaml          # Web 界面配置（预留）
└── desktop.yaml         # 桌面应用配置（预留）
```

## 配置文件说明

### live2d.yaml

Live2D 模型渲染与交互配置。

**核心功能**:
- 模型加载与位置调整
- 表情映射（AI 情感 → Live2D 表情）
- 动作触发（待机、交互、语音）
- 物理引擎模拟
- 渲染优化

**使用场景**:
- TypeScript 前端集成 Live2D
- 虚拟主播形象展示
- 情感可视化反馈

### audio.yaml

TTS 语音合成与音频播放配置。

**核心功能**:
- 多 TTS 引擎支持（Azure/Edge/VITS）
- 语音参数调节（语速、音调、音量）
- 音效管理（情感音效映射）
- 音频缓存优化
- 流式播放支持

**使用场景**:
- AI 语音回复
- 情感音效播放
- 离线 TTS 合成

## 使用方式

### TypeScript/Node.js

```typescript
import { loadConfig } from '@cradle-selrena/core';

// 加载 Live2D 配置
const live2dConfig = await loadConfig('platforms/live2d.yaml');

// 加载 Audio 配置
const audioConfig = await loadConfig('platforms/audio.yaml');

// 合并配置
const platformConfig = {
  live2d: live2dConfig.live2d,
  audio: audioConfig.audio,
};
```

### Python（跨语言调用）

```python
from pathlib import Path
import yaml

# 加载配置
config_path = Path("configs/platforms/live2d.yaml")
with open(config_path, "r", encoding="utf-8") as f:
    live2d_config = yaml.safe_load(f)

# 通过事件总线传递给 TS 层
# （使用 global_event_bus 发布配置更新事件）
```

## 配置优先级

```
环境变量 > 平台配置文件 > 默认值
```

## 扩展新平台

1. 在 `platforms/` 下创建新的配置文件（如 `web-ui.yaml`）
2. 定义平台特定的 Schema 模型
3. 在平台代码中加载并使用配置

## 注意事项

- Platforms 层配置**不**影响 Python AI 核心逻辑
- 仅当前端启用对应平台时才需要配置
- 生产环境建议禁用调试功能（如物理引擎可视化）
