# Cradle_Selrena (摇篮·月见)

本项目使用 **NapCat** 作为 OneBot‑11 服务器/客户端，
通过 WebSocket 与 QQ 服务通信。

## 模块开关与配置

配置文件 `configs/settings.yaml` 现在为各个子系统提供了
独立开关，方便在不同环境下灵活启用或禁用。示例如下：

```yaml
perception:
  audio:
    enabled: true            # 整体麦克风/ASR 功能
    sample_rate: 16000
    chunk_size: 1024
    device_index: null
    asr:
      enabled: true          # ASR 本身的开关（还需启用 audio）
      model_dir: iic/SenseVoiceSmall
      device: cuda
      quantize: true
      use_itn: true
  vision:
    enabled: true            # 视觉捕捉 (目前仅占位)
    capture_interval: 5.0
presentation:
  tts:
    enabled: true            # 是否启用语音合成与播放
    engine: edge-tts
    …
  vts:
    enabled: false           # 虚拟形象 (VTS) 桥接
    host: 127.0.0.1
    port: 8001
# 新增：感知层相关配置项
sensory:
  strict_wake: false        # 如果为 true，只有包含唤醒词的语音/文字才进入意识流
                           # (默认是启动后30秒内的任何讲话都会通过)
napcat:
  enable: true              # OneBot/QQ 客户端
  …
```

只要在配置中将 `enabled`/`enable` 设为 `false`，对应组件
在启动时就会被跳过，模块内部也会做额外检查以避免执行
不必要的逻辑。

## Napcat 配置

配置位于 `configs/settings.yaml` 下的 `napcat` 节：

```yaml
napcat:
  enable: true            # 是否启用 Napcat 支持
  listen_port: 6200       # 由 Selrena 监听的本地端口（示例改为 6200 避免占用）
  token: "0927elise"     # 和 NapCat 客户端的 verifyKey 保持一致
```

- 当前仅支持 **服务器模式**（Selrena 扮演 OneBot 主机）。
- 当启用后，系统内部会自动安装 `NapcatResponder`，它会
  **从收到的消息中提取发送者 ID 并在灵魂说话时自动回复**。
  译者注意：客户端会将 `user_id` 字段加入到框架的
  `input.user_message` 事件载荷，如果原始 OneBot 事件中有
  嵌套 `sender.user_id`、顶级 `user_id` 等，都能被识别。
- 服务器会在握手阶段检查 WebSocket 子协议。Napcat 客户端
  一般在 `Sec-WebSocket-Protocol` 首部中发送 `onebot` 或
  `onebot,<token>`。
  
  * 由于部分 WebSocket 库会拒绝逗号分隔的协议字符串，
    Selrena 通过 **自定义子协议选择器** 来兼容这种用法。
  * 如果你自己用手动脚本测试，请将含逗号的值写入
    `Sec-WebSocket-Protocol` 头部而不是 `subprotocols` 参数；
    可以参考 `scripts/napcat_test.py`。
  * 日志会记录客户端请求的协议及任何令牌验证结果，便于
    调试握手失败、`ECONNRESET` 或 `no subprotocols supported`
    等错误。

当 Napcat 启用时，
`src/cradle/selrena/synapse/napcat_server.py` 会在启动时自动
创建 WebSocket 服务并将接收的 OneBot 事件发布到
`global_event_bus`（主题 `napcat.event`）。

上层可以订阅相同主题处理消息，或者通过发布
`napcat.send` 事件向所有连接的客户端广播数据。

此外，`src/cradle/selrena/vessel/napcat/napcat_client.py` 提供了
一个简单的适配层，会把收到的 QQ/OneBot 消息转换为框架
内部的 `input.user_message` 事件，用于天然支持月见的
交互流程。内核启动时实例化并初始化它即可。

通过开启 `debug` 可以输出消息级别的调试日志；这在
开发或排查握手/数据问题时非常有用。

```python
# 发送给 NapCat
# 在服务器模式下直接通过事件总线发布 napcat.send 事件即可
# await global_event_bus.publish(BaseEvent(name="napcat.send", payload={"api": "send_message", "params": {...}}))
# 或者使用 NapcatClient 提供的辅助方法：
#
# ```python
# client = NapcatClient()
# await client.initialize()
# await client.send_api("send_private_msg", {"user_id": uid, "message": "hi"})
# # 或者更简单：
# await client.reply(uid, "hi")
#
# 如果你希望回复逻辑与灵魂思考完全解耦，可以启用
# ``NapcatResponder`` 组件。
# 它自动检测最近的 ``input.user_message`` 发送者，并在
# ``action.presentation.speak`` 时将文本回发给 QQ。
# 空白或仅含 ``None`` 的说话事件会被忽略，避免无意义
# 消息出现在聊天中。
# 如果最后一条来自群聊，NapcatResponder 会转为使用
# ``send_group_msg`` 而不是私聊回复，从而保持话题在群内。
# 该组件已由代码自动在 Napcat 服务器模式下注册，无需手动
# 修改配置文件。# ```

# 监听来自 NapCat 的消息
global_event_bus.subscribe('napcat.event', handler)
```

## 测试

* `scripts/napcat_test.py` 可用于独立验证 WebSocket
  连接与认证。新版本支持 `--format array|object` 以便测试
  不同的消息格式。

> 注意：当前月见仅作为 Napcat 服务端运行，不再包含客户端连接逻辑。