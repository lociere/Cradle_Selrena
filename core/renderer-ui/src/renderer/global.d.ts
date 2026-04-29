interface MessageChunk {
  trace_id: string;
  content: string;
  is_final: boolean;
}

interface EmotionStatePayload {
  emotion_type: string;
  intensity: number;
  trigger: string;
  timestamp: string;
}

interface ClientPerceptionEvent {
  content: string;
  source: string;
}

interface ConnectionStatus {
  status: 'online' | 'offline';
}

interface AvatarShellStatus {
  shellKind: 'placeholder-puppet' | 'unity-shell';
}

interface SelrenaAPI {
  sendPerception: (event: ClientPerceptionEvent) => Promise<void>;
  onMessageStream: (callback: (chunk: MessageChunk) => void) => void;
  onEmotionUpdate: (callback: (emotion: EmotionStatePayload) => void) => void;
  onConnectionStatus: (callback: (status: ConnectionStatus) => void) => void;
  onAvatarShellStatus: (callback: (status: AvatarShellStatus) => void) => void;
}

declare global {
  interface Window {
    selrenaAPI: SelrenaAPI;
  }
}

export {};
