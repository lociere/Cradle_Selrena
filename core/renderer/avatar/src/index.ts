import fs from 'node:fs/promises';
import path from 'node:path';
import WebSocket from 'ws';

type AvatarShellKind = 'placeholder-puppet' | 'unity-shell';

interface UnityDownstreamFrame {
  type: 'visual_command' | 'audio_push' | 'ping';
  timestamp: number;
  data?: unknown;
}

interface ShellState {
  shellKind: AvatarShellKind;
  connected: boolean;
  lastCommandType: string | null;
  lastExpression: string | null;
  lastMotion: string | null;
  updatedAt: string;
}

const AVATAR_ENGINE_URL = process.env.SELRENA_AVATAR_ENGINE_URL ?? 'ws://127.0.0.1:8082';
const HEARTBEAT_INTERVAL_MS = 5000;
const RECONNECT_INTERVAL_MS = 2500;
const REPO_ROOT = path.resolve(__dirname, '..', '..', '..', '..');
const STATE_FILE_PATH = path.resolve(REPO_ROOT, 'runtime', 'temp', 'avatar-shell-state.json');

let socket: WebSocket | null = null;
let heartbeatTimer: NodeJS.Timeout | null = null;
let reconnectTimer: NodeJS.Timeout | null = null;

const state: ShellState = {
  shellKind: 'unity-shell',
  connected: false,
  lastCommandType: null,
  lastExpression: null,
  lastMotion: null,
  updatedAt: new Date().toISOString(),
};

async function persistState(): Promise<void> {
  await fs.mkdir(path.dirname(STATE_FILE_PATH), { recursive: true });
  state.updatedAt = new Date().toISOString();
  await fs.writeFile(STATE_FILE_PATH, `${JSON.stringify(state, null, 2)}\n`, 'utf-8');
}

function scheduleReconnect(): void {
  if (reconnectTimer) {
    return;
  }

  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    connect();
  }, RECONNECT_INTERVAL_MS);
}

async function markDisconnected(): Promise<void> {
  state.connected = false;
  await persistState();
}

function startHeartbeat(): void {
  if (heartbeatTimer) {
    clearInterval(heartbeatTimer);
  }

  heartbeatTimer = setInterval(() => {
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      return;
    }

    socket.send(JSON.stringify({
      type: 'heartbeat',
      data: {
        ready: true,
      },
    }));
  }, HEARTBEAT_INTERVAL_MS);
}

async function handleFrame(frame: UnityDownstreamFrame): Promise<void> {
  if (frame.type === 'ping') {
    socket?.send(JSON.stringify({
      type: 'heartbeat',
      data: {
        ready: true,
      },
    }));
    return;
  }

  if (frame.type !== 'visual_command') {
    return;
  }

  const payload = (frame.data ?? {}) as {
    commandType?: string;
    expression?: { expression_id?: string };
    motion?: { motion_id?: string };
  };

  state.lastCommandType = payload.commandType ?? null;
  state.lastExpression = payload.expression?.expression_id ?? null;
  state.lastMotion = payload.motion?.motion_id ?? null;
  await persistState();
}

function connect(): void {
  socket = new WebSocket(AVATAR_ENGINE_URL);

  socket.on('open', async () => {
    state.connected = true;
    await persistState();

    socket?.send(JSON.stringify({
      type: 'status',
      data: {
        ready: true,
        shell_kind: state.shellKind,
      },
    }));

    startHeartbeat();
  });

  socket.on('message', async (raw: WebSocket.RawData) => {
    try {
      const frame = JSON.parse(raw.toString()) as UnityDownstreamFrame;
      await handleFrame(frame);
    } catch (error) {
      console.warn('[renderer-avatar] failed to parse frame', error);
    }
  });

  socket.on('close', async () => {
    await markDisconnected();
    scheduleReconnect();
  });

  socket.on('error', async () => {
    await markDisconnected();
    scheduleReconnect();
  });
}

async function shutdown(): Promise<void> {
  if (heartbeatTimer) {
    clearInterval(heartbeatTimer);
    heartbeatTimer = null;
  }
  if (reconnectTimer) {
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }
  if (socket) {
    socket.close();
    socket = null;
  }
  await markDisconnected();
}

void persistState().then(() => {
  connect();
});

process.on('SIGINT', () => {
  void shutdown().finally(() => process.exit(0));
});

process.on('SIGTERM', () => {
  void shutdown().finally(() => process.exit(0));
});