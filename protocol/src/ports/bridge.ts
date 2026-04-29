// plugin standard interface — scene and perception routing types

import {
  MessageSourceMeta,
  MessageSourceType,
  SceneRoutingHint,
  SceneSessionPolicy,
} from "../ipc/ipc-types";

export type PluginLogLevel = "debug" | "info" | "warn" | "error" | "critical";

export type PluginTranscriptSceneScope = "group_scene" | "private_session" | "custom";

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

export interface PluginSceneTranscriptEntry {
  root_dir?: string;
  scene_scope: PluginTranscriptSceneScope;
  scene_type: "group" | "private" | "channel" | "custom";
  transcript_scene_id: string;
  identity_scope?: string;
  owner_id?: string;
  owner_label?: string;
  summary?: string;
  role: "user" | "assistant" | "system";
  speaker: string;
  content: string;
  tags?: string[];
  occurred_at?: string;
}
