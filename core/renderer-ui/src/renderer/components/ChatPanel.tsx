import React, { useState, useRef, useEffect } from 'react';
import { useAppStore, type ChatMessage } from '../store/appStore';

export const ChatPanel: React.FC = () => {
  const messages = useAppStore((s) => s.messages);
  const isStreaming = useAppStore((s) => s.isStreaming);
  const currentStreamText = useAppStore((s) => s.currentStreamText);
  const addUserMessage = useAppStore((s) => s.addUserMessage);

  const [input, setInput] = useState('');
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [messages, currentStreamText]);

  const handleSend = (): void => {
    const text = input.trim();
    if (!text) return;

    addUserMessage(text);
    setInput('');

    const api = window.selrenaAPI;
    if (api) {
      api.sendPerception({ content: text, source: 'chat_input' });
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent): void => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="chat-panel">
      <div className="chat-list" ref={listRef}>
        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}
        {isStreaming && currentStreamText && (
          <MessageBubble
            message={{
              id: '__streaming',
              role: 'assistant',
              content: currentStreamText,
              timestamp: Date.now(),
            }}
            isStreaming
          />
        )}
      </div>

      <div className="chat-input-row">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="说点什么..."
          className="chat-input"
        />
        <button onClick={handleSend} className="send-btn">
          发送
        </button>
      </div>
    </div>
  );
};

const MessageBubble: React.FC<{
  message: ChatMessage;
  isStreaming?: boolean;
}> = ({ message, isStreaming }) => {
  const isUser = message.role === 'user';
  return (
    <div className={`bubble-row ${isUser ? 'bubble-row-user' : 'bubble-row-assistant'}`}>
      <div className={`bubble ${isUser ? 'bubble-user' : 'bubble-assistant'}`}>
        {message.content}
        {isStreaming && <span className="stream-caret">▊</span>}
      </div>
    </div>
  );
};
