// 这个文件是示例，可以直接删除。
// src/ 下的代码结构由你自定。

/**
 * 【可选】仅平台特化适配器插件需要 cortex/ 目录。
 * 如果您的插件是工具类、感知推送类及其他类型，请删除此目录。
 *
 * ── Cortex 层职责 ──────────────────────────────────────────────
 *
 * 1. 接收平台原始数据（脏数据）
 * 2. 清洗、归一化为系统标准格式（CortexOutput）
 * 3. 只做数据格式转换，不含任何业务判断（是否回复、是否记忆等逻辑属于主插件类）
 * 4. 所有输出通过返回值传递，不直接调用 ctx
 *
 * ── AI Core / Adapter 边界强制规则 ─────────────────────────────
 *
 * 平台私有字段（如 QQ 号、Discord 用户 ID、群组 ID）必须
 * 在此层内转换为通用语义字段后丢弃，严禁通过 PerceptionEvent.content
 * 上传至 AI Core。AI Core 层仅允许配置的通用路由字段。
 */

/** Cortex 输出：经清洗的语义内容和元数据，不含任何平台私有路由字段 */
export interface CortexOutput {
  /** 主文本，已格式化为可供 AI Core 阅读的语义字符串 */
  formattedText: string;
  /** 模态类型（text / image / audio / video）*/
  modality: string[];
  /** 熟悉度/亲密度（0–10）*/
  familiarity: number;
}

/**
 * 示例：将平台原始消息归一化为 CortexOutput。
 * 无法处理时返回 null。
 */
export function normalizePlatformMessage(rawEvent: unknown): CortexOutput | null {
  if (!rawEvent || typeof rawEvent !== 'object') return null;
  const event = rawEvent as Record<string, unknown>;

  // TODO: 按具体平台协议实现归一化逻辑
  const text = String(event['text'] ?? '').trim();
  if (!text) return null;

  return {
    formattedText: text,
    modality: ['text'],
    familiarity: 5,
  };
}
