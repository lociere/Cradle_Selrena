// Public exports for protocol package

export * from './core';
export * from './models';
export * from './events';
export * from './ports';
export * from './ipc/ipc-types';
export type { PerceptionMessageRequest, PerceptionModalityItem } from './ipc/ipc-types';
export * from './config/schema';

// Schema-First 自动生成的契约类型
export * from './generated';

// Plugin system exports
export * from './plugin/plugin-manifest.schema';
export * from './plugin/plugin-events';
export * from './plugin/sdk';
