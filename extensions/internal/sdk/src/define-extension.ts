import type { ExtensionManifest, SystemExtension } from '@cradle-selrena/protocol';

export interface ExtensionDefinition<TConfig = unknown> {
  extension: SystemExtension<TConfig>;
  manifest?: Partial<ExtensionManifest>;
}

export function defineExtension<TConfig = unknown>(
  definition: ExtensionDefinition<TConfig>,
): ExtensionDefinition<TConfig> {
  return definition;
}
