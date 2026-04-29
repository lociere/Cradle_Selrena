import { contextBridge, ipcRenderer } from 'electron';

export interface MessageChunk {
  trace_id: string;
  content: string;
  is_final: boolean;
}

export interface EmotionStatePayload {
  emotion_type: string;
  intensity: number;
  trigger: string;
  timestamp: string;
}

export interface ClientPerceptionEvent {
  content: string;
  source: string;
}

export interface ConnectionStatus {
  status: 'online' | 'offline';
}

export interface AvatarShellStatus {
  shellKind: 'placeholder-puppet' | 'unity-shell';
}

contextBridge.exposeInMainWorld('selrenaAPI', {
  sendPerception: (event: ClientPerceptionEvent): Promise<void> =>
    ipcRenderer.invoke('ui:send-perception', event),

  onMessageStream: (callback: (chunk: MessageChunk) => void): void => {
    ipcRenderer.on('ui:message-stream', (_e, data) => callback(data));
  },

  onEmotionUpdate: (callback: (emotion: EmotionStatePayload) => void): void => {
    ipcRenderer.on('ui:emotion-update', (_e, data) => callback(data));
  },

  onConnectionStatus: (callback: (status: ConnectionStatus) => void): void => {
    ipcRenderer.on('ui:connection-status', (_e, data) => callback(data));
  },

  onAvatarShellStatus: (callback: (status: AvatarShellStatus) => void): void => {
    ipcRenderer.on('ui:avatar-shell-status', (_e, data) => callback(data));
  },
});
