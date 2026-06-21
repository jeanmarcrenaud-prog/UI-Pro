// components/agent/SuccessConfetti.tsx
'use client';

import confetti from 'canvas-confetti';
import { useEffect, useRef } from 'react';

interface SuccessConfettiProps {
  trigger: boolean;
  intensity?: 'low' | 'medium' | 'high';
}

export default function SuccessConfetti({ trigger, intensity = 'medium' }: SuccessConfettiProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!trigger) return;

    const container = containerRef.current;
    if (!container) return;

    const rect = container.getBoundingClientRect();
    const canvasCenterX = rect.left + rect.width / 2;
    const canvasCenterY = rect.top + rect.height * 0.45;

    const count = intensity === 'high' ? 280 : intensity === 'medium' ? 160 : 90;

    const baseOptions = {
      colors: ['#22d3ee', '#67e8f9', '#4ade80', '#a78bfa', '#f472b6', '#fbbf24'],
    };

    // Main centred burst
    confetti({
      ...baseOptions,
      origin: {
        x: (canvasCenterX + (Math.random() - 0.5) * rect.width * 0.6) / window.innerWidth,
        y: (canvasCenterY + (Math.random() - 0.5) * rect.height * 0.4) / window.innerHeight,
      },
      particleCount: Math.floor(count * 0.6),
      spread: 80,
      startVelocity: 55,
    });

    // Wider secondary burst from same origin
    confetti({
      ...baseOptions,
      origin: {
        x: (canvasCenterX + (Math.random() - 0.5) * rect.width * 0.6) / window.innerWidth,
        y: (canvasCenterY + (Math.random() - 0.5) * rect.height * 0.4) / window.innerHeight,
      },
      particleCount: Math.floor(count * 0.3),
      spread: 110,
      startVelocity: 45,
      decay: 0.9,
    });

    // Left side burst
    setTimeout(() => {
      confetti({
        ...baseOptions,
        origin: {
          x: (rect.left + rect.width * 0.25) / window.innerWidth,
          y: (canvasCenterY - 40) / window.innerHeight,
        },
        particleCount: 60,
        spread: 70,
      });
    }, 120);

    // Right side burst
    setTimeout(() => {
      confetti({
        ...baseOptions,
        origin: {
          x: (rect.left + rect.width * 0.75) / window.innerWidth,
          y: (canvasCenterY - 30) / window.innerHeight,
        },
        particleCount: 60,
        spread: 70,
      });
    }, 220);
  }, [trigger, intensity]);

  return <div ref={containerRef} className="absolute inset-0 pointer-events-none" />;
}
