import type { PluginManifest, SystemPlugin } from '@cradle-selrena/protocol';

export interface ExtensionDefinition<TConfig = unknown> {
  plugin: SystemPlugin<TConfig>;
  manifest?: Partial<PluginManifest>;
}

export function defineExtension<TConfig = unknown>(
  definition: ExtensionDefinition<TConfig>,
): ExtensionDefinition<TConfig> {
  return definition;
}