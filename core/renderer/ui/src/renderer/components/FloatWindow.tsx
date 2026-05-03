import React from 'react';
import { Live2DCanvas } from './Live2DCanvas';
import { ChatPanel } from './ChatPanel';
import { useAppStore } from '../store/appStore';
import { useEmotionStore } from '../store/emotionStore';

export const FloatWindow: React.FC = () => {
  const systemStatus = useAppStore((s) => s.systemStatus);
  const avatarShellKind = useAppStore((s) => s.avatarShellKind);
  const lastEmotion = useEmotionStore((s) => s.lastEmotion);

  return (
    <div className="shell-root">
      <div className="shell-drag-layer" />

      <div className="shell-header">
        <div className="brand-block" style={{ WebkitAppRegion: 'drag' } as React.CSSProperties}>
          <span className="brand-name">Selrena</span>
          <span className={`status-pill status-${systemStatus}`}>{systemStatus}</span>
        </div>
        <div className="shell-meta" style={{ WebkitAppRegion: 'no-drag' } as React.CSSProperties}>
          <span className="shell-chip">kernel: {systemStatus}</span>
          <span className="shell-chip">avatar: {avatarShellKind}</span>
          <span className="emotion-readout">emotion: {lastEmotion?.emotion_type ?? 'neutral'}</span>
        </div>
      </div>

      <div className="visual-stage">
        <Live2DCanvas />
      </div>

      <div className="chat-stage" style={{ WebkitAppRegion: 'no-drag' } as React.CSSProperties}>
        <ChatPanel />
      </div>
    </div>
  );
};
