import { z } from 'zod';
import { Permission } from '../core';

export const ExtensionKindSchema = z.enum([
  'adapter',
  'renderer',
  'tool',
  'integration',
]);

export const ActivationEventSchema = z.string().min(1);

export const ExtensionCommandContributionSchema = z.object({
  command: z.string().min(1),
  title: z.string().min(1),
  category: z.string().optional(),
});

export const ExtensionContributionSchema = z.object({
  commands: z.array(ExtensionCommandContributionSchema).default([]),
});

export const ExtensionManifestSchema = z.object({
  id: z.string(),
  name: z.string(),
  version: z.string(),
  description: z.string().optional(),
  author: z.string().optional(),
  category: z.string().optional(),
  tags: z.array(z.string()).default([]),
  main: z.string(),
  minAppVersion: z.string().default('0.0.0'),
  permissions: z.array(z.nativeEnum(Permission)).default([]),
  extensionKind: ExtensionKindSchema.default('integration'),
  activationEvents: z.array(ActivationEventSchema).default(['onStartup']),
  contributes: ExtensionContributionSchema.default({ commands: [] }),
});

export type ExtensionManifest = z.infer<typeof ExtensionManifestSchema>;
export type ExtensionKind = z.infer<typeof ExtensionKindSchema>;
export type ActivationEvent = z.infer<typeof ActivationEventSchema>;
export type ExtensionCommandContribution = z.infer<typeof ExtensionCommandContributionSchema>;
export type ExtensionContribution = z.infer<typeof ExtensionContributionSchema>;

