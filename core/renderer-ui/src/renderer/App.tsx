import React, { useEffect } from 'react';
import { FloatWindow } from './components/FloatWindow';
import { useAppStore } from './store/appStore';
import { useEmotionStore } from './store/emotionStore';

export default function App(): React.JSX.Element {
  const appendMessageChunk = useAppStore((s) => s.appendMessageChunk);
  const setSystemStatus = useAppStore((s) => s.setSystemStatus);
  const setAvatarShellKind = useAppStore((s) => s.setAvatarShellKind);
  const updateEmotion = useEmotionStore((s) => s.updateEmotion);

  useEffect(() => {
    const api = window.selrenaAPI;
    setAvatarShellKind('placeholder-puppet');

    if (!api) {
      setSystemStatus('offline');
      return;
    }

    setSystemStatus('connecting');

    api.onMessageStream((chunk) => {
      appendMessageChunk(chunk.trace_id, chunk.content, chunk.is_final);
    });

    api.onEmotionUpdate((emotion) => {
      updateEmotion(emotion);
    });

    api.onConnectionStatus((status) => {
      setSystemStatus(status.status === 'online' ? 'online' : 'offline');
    });

    api.onAvatarShellStatus((status) => {
      setAvatarShellKind(status.shellKind);
    });
  }, [appendMessageChunk, setAvatarShellKind, setSystemStatus, updateEmotion]);

  return <FloatWindow />;
}
