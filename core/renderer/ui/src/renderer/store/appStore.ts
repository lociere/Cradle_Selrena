import { create } from 'zustand';

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
}

export type SystemStatus = 'connecting' | 'online' | 'offline' | 'error';
export type UIMode = 'float' | 'fullscreen';
export type AvatarShellKind = 'placeholder-puppet' | 'unity-shell';

interface AppState {
  messages: ChatMessage[];
  isStreaming: boolean;
  currentStreamText: string;
  currentTraceId: string | null;
  systemStatus: SystemStatus;
  uiMode: UIMode;
  avatarShellKind: AvatarShellKind;

  appendMessageChunk: (traceId: string, chunk: string, isFinal: boolean) => void;
  addUserMessage: (content: string) => void;
  clearChat: () => void;
  setSystemStatus: (status: SystemStatus) => void;
  setUIMode: (mode: UIMode) => void;
  setAvatarShellKind: (kind: AvatarShellKind) => void;
}

let messageIdCounter = 0;
const nextId = (): string => `msg_${Date.now()}_${++messageIdCounter}`;

export const useAppStore = create<AppState>((set, get) => ({
  messages: [],
  isStreaming: false,
  currentStreamText: '',
  currentTraceId: null,
  systemStatus: 'connecting',
  uiMode: 'float',
  avatarShellKind: 'placeholder-puppet',

  appendMessageChunk: (traceId: string, chunk: string, isFinal: boolean) => {
    const state = get();
    if (!state.isStreaming || state.currentTraceId !== traceId) {
      // New stream started
      if (isFinal) {
        set({
          messages: [
            ...state.messages,
            { id: nextId(), role: 'assistant', content: chunk, timestamp: Date.now() },
          ],
          isStreaming: false,
          currentStreamText: '',
          currentTraceId: null,
        });
      } else {
        set({
          isStreaming: true,
          currentStreamText: chunk,
          currentTraceId: traceId,
        });
      }
    } else {
      // Continue existing stream
      const newText = state.currentStreamText + chunk;
      if (isFinal) {
        set({
          messages: [
            ...state.messages,
            { id: nextId(), role: 'assistant', content: newText, timestamp: Date.now() },
          ],
          isStreaming: false,
          currentStreamText: '',
          currentTraceId: null,
        });
      } else {
        set({ currentStreamText: newText });
      }
    }
  },

  addUserMessage: (content: string) => {
    set((state) => ({
      messages: [
        ...state.messages,
        { id: nextId(), role: 'user', content, timestamp: Date.now() },
      ],
    }));
  },

  clearChat: () =>
    set({ messages: [], currentStreamText: '', isStreaming: false, currentTraceId: null }),

  setSystemStatus: (status) => set({ systemStatus: status }),

  setUIMode: (mode) => set({ uiMode: mode }),

  setAvatarShellKind: (kind) => set({ avatarShellKind: kind }),
}));
