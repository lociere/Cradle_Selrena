import { ipcMain, BrowserWindow } from 'electron';
import WebSocket from 'ws';

const KERNEL_WS_URL = process.env.SELRENA_DESKTOP_UI_WS_URL ?? 'ws://127.0.0.1:8083';
const RECONNECT_INTERVAL_MS = 3000;

let kernelSocket: WebSocket | null = null;
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
let rendererWindow: BrowserWindow | null = null;

function connectToKernel(): void {
  if (kernelSocket?.readyState === WebSocket.OPEN) return;

  try {
    kernelSocket = new WebSocket(KERNEL_WS_URL);
  } catch {
    scheduleReconnect();
    return;
  }

  kernelSocket.on('open', () => {
    console.log('[ipc-bridge] Connected to kernel WebSocket');
    sendToRenderer('ui:connection-status', { status: 'online' });
  });

  kernelSocket.on('message', (raw: WebSocket.RawData) => {
    try {
      const data = JSON.parse(raw.toString());
      if (data.type === 'chat_reply') {
        sendToRenderer('ui:message-stream', {
          trace_id: `trace_${Date.now()}`,
          content: data.text ?? '',
          is_final: true,
        });

        if (data.emotionState) {
          sendToRenderer('ui:emotion-update', {
            emotion_type: data.emotionState.emotion_type ?? 'neutral',
            intensity: data.emotionState.intensity ?? 0.5,
            trigger: data.emotionState.trigger ?? '',
            timestamp: new Date().toISOString(),
          });
        }
      } else if (data.type === 'avatar_shell_status') {
        sendToRenderer('ui:avatar-shell-status', {
          shellKind: data.shellKind === 'unity-shell' ? 'unity-shell' : 'placeholder-puppet',
        });
      } else if (data.type === 'pong') {
        // heartbeat ack, ignore
      }
    } catch {
      console.warn('[ipc-bridge] Failed to parse kernel message');
    }
  });

  kernelSocket.on('close', () => {
    console.log('[ipc-bridge] Kernel WebSocket closed');
    sendToRenderer('ui:connection-status', { status: 'offline' });
    kernelSocket = null;
    scheduleReconnect();
  });

  kernelSocket.on('error', (err: Error) => {
    console.warn('[ipc-bridge] Kernel WebSocket error:', err.message);
    kernelSocket?.close();
    kernelSocket = null;
  });
}

function scheduleReconnect(): void {
  if (reconnectTimer) return;
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    connectToKernel();
  }, RECONNECT_INTERVAL_MS);
}

function sendToRenderer(channel: string, data: unknown): void {
  if (rendererWindow && !rendererWindow.isDestroyed()) {
    rendererWindow.webContents.send(channel, data);
  }
}

export function registerIPCHandlers(win: BrowserWindow): void {
  rendererWindow = win;

  ipcMain.handle('ui:send-perception', async (_event, payload: unknown) => {
    const content = (payload as { content?: string })?.content ?? '';

    if (kernelSocket?.readyState === WebSocket.OPEN) {
      kernelSocket.send(JSON.stringify({ type: 'chat_input', text: content }));
    } else {
      sendToRenderer('ui:message-stream', {
        trace_id: `trace_${Date.now()}`,
        content: '⚠ 内核未连接，请确保 Kernel 已启动',
        is_final: true,
      });
    }
  });

  connectToKernel();
}

export function disconnectKernel(): void {
  if (reconnectTimer) {
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }
  if (kernelSocket) {
    kernelSocket.close();
    kernelSocket = null;
  }
}
