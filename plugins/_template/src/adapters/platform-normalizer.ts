/**
 * Adapter/Cortex 示例 — src/adapters/platform-normalizer.ts
 *
 * Adapters 层（Vessel Cortex）职责：
 *   - 接收平台原始数据（脏数据）
 *   - 清洗、归一化为系统标准格式（PerceptionEvent、plain object）
 *   - 只做数据转换，不含业务判断（是否应该回复、是否触发记忆等）
 *   - 不直接调用 pluginContext，所有输出通过返回值传递
 *
 * 架构原则：
 *   Soul 层只接受标准 PerceptionEvent，平台私有字段
 *   必须在此层转换为通用字段（vessel_id / source_type / source_id）后丢弃。
 */

export interface NormalizedEvent {
  sourceType: string;
  sourceId: string;
  text: string;
}

/**
 * 示例：归一化平台原始消息为系统标准格式。
 * 无法处理时返回 null。
 */
export function normalizePlatformEvent(rawEvent: unknown): NormalizedEvent | null {
  if (!rawEvent || typeof rawEvent !== 'object') return null;

  const event = rawEvent as Record<string, unknown>;

  // TODO: 根据具体平台协议实现归一化逻辑
  return {
    sourceType: 'unknown',
    sourceId: String(event['id'] ?? ''),
    text: String(event['text'] ?? ''),
  };
}
