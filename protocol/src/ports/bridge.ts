import {
  MessageSourceMeta,
  MessageSourceType,
  SceneRoutingHint,
  SceneSessionPolicy,
} from '../ipc/ipc-types';

export type ExtensionLogLevel = 'debug' | 'info' | 'warn' | 'error' | 'critical';

export type ExtensionTranscriptSceneScope = 'group_scene' | 'private_session' | 'custom';

export interface SceneRoutingRequest {
  source: MessageSourceMeta;
  routing?: SceneRoutingHint;
}

export interface SceneRoutingResult {
  scene_id: string;
  source: MessageSourceMeta;
  source_type: MessageSourceType;
  source_id: string;
  actor_id?: string;
  actor_name?: string;
  session_policy: SceneSessionPolicy;
}

export interface ExtensionSceneTranscriptEntry {
  root_dir?: string;
  scene_scope: ExtensionTranscriptSceneScope;
  scene_type: 'group' | 'private' | 'channel' | 'custom';
  transcript_scene_id: string;
  identity_scope?: string;
  owner_id?: string;
  owner_label?: string;
  summary?: string;
  role: 'user' | 'assistant' | 'system';
  speaker: string;
  content: string;
  tags?: string[];
  occurred_at?: string;
}

