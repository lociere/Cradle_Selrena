import React, { useRef, useEffect } from 'react';
import { useEmotionStore } from '../store/emotionStore';

export const Live2DCanvas: React.FC = () => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const params = useEmotionStore((s) => s.params);
  const lastEmotion = useEmotionStore((s) => s.lastEmotion);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const resize = (): void => {
      canvas.width = canvas.parentElement?.clientWidth ?? 400;
      canvas.height = canvas.parentElement?.clientHeight ?? 400;
    };
    resize();
    window.addEventListener('resize', resize);

    let animationFrame = 0;

    const render = (time: number): void => {
      const width = canvas.width;
      const height = canvas.height;
      const cx = width / 2;
      const cy = height / 2 - 6;
      const blink = 0.65 + 0.35 * Math.abs(Math.sin(time / 1400));
      const breath = Math.sin(time / 1100) * 5;
      const haloPulse = 16 + Math.sin(time / 900) * 4;
      const eyeHeight = Math.max(2, 9 * params.eyeOpenness * blink);
      const mouthArc = Math.max(0.12, Math.min(0.95, params.mouthForm));

      ctx.clearRect(0, 0, width, height);

      const stageGradient = ctx.createRadialGradient(cx, cy - 30, 20, cx, cy, width * 0.45);
      stageGradient.addColorStop(0, 'rgba(102, 221, 184, 0.22)');
      stageGradient.addColorStop(1, 'rgba(0, 0, 0, 0)');
      ctx.fillStyle = stageGradient;
      ctx.fillRect(0, 0, width, height);

      ctx.beginPath();
      ctx.arc(cx, cy - 26, 92 + haloPulse, 0, Math.PI * 2);
      ctx.strokeStyle = 'rgba(138, 247, 208, 0.14)';
      ctx.lineWidth = 1.5;
      ctx.stroke();

      ctx.fillStyle = 'rgba(255, 255, 255, 0.06)';
      ctx.beginPath();
      ctx.ellipse(cx, cy + 120, 76, 16, 0, 0, Math.PI * 2);
      ctx.fill();

      ctx.fillStyle = 'rgba(77, 176, 233, 0.18)';
      ctx.beginPath();
      ctx.roundRect(cx - 46, cy + 24 + breath, 92, 102, 28);
      ctx.fill();

      ctx.beginPath();
      ctx.arc(cx, cy + breath, 62, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(255, 212, 220, ${0.34 + params.blushLevel * 0.35})`;
      ctx.fill();
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.28)';
      ctx.lineWidth = 2;
      ctx.stroke();

      ctx.fillStyle = 'rgba(255, 255, 255, 0.82)';
      ctx.fillRect(cx - 25, cy - 12 + breath, 14, eyeHeight);
      ctx.fillRect(cx + 11, cy - 12 + breath, 14, eyeHeight);

      ctx.beginPath();
      ctx.arc(cx - 35, cy + 11 + breath, 10, 0, Math.PI * 2);
      ctx.arc(cx + 35, cy + 11 + breath, 10, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(255, 120, 148, ${0.08 + params.blushLevel * 0.24})`;
      ctx.fill();

      ctx.beginPath();
      ctx.arc(cx, cy + 21 + breath, 17, 0, Math.PI * mouthArc);
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.72)';
      ctx.lineWidth = 2.5;
      ctx.stroke();

      ctx.fillStyle = 'rgba(233, 255, 246, 0.55)';
      ctx.font = '12px Outfit, sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(`avatar shell placeholder`, cx, height - 28);
      ctx.fillStyle = 'rgba(233, 255, 246, 0.36)';
      ctx.fillText(
        `${params.motionGroup}${lastEmotion ? ` / ${lastEmotion.emotion_type}` : ''}`,
        cx,
        height - 12,
      );

      animationFrame = window.requestAnimationFrame(render);
    };

    animationFrame = window.requestAnimationFrame(render);

    return () => {
      window.cancelAnimationFrame(animationFrame);
      window.removeEventListener('resize', resize);
    };
  }, [lastEmotion, params]);

  return (
    <canvas
      ref={canvasRef}
      style={{
        width: '100%',
        height: '100%',
        display: 'block',
      }}
    />
  );
};
