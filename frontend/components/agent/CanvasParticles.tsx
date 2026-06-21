// components/agent/CanvasParticles.tsx
'use client';

import { useEffect, useRef } from 'react';

interface CanvasParticlesProps {
  isActive?: boolean;
  className?: string;
}

interface ParticleState {
  x: number;
  y: number;
  size: number;
  speedX: number;
  speedY: number;
  opacity: number;
  color: string;
  life: number;
}

function createParticle(x: number, y: number, isBurst = false): ParticleState {
  return {
    x,
    y,
    size: isBurst ? Math.random() * 3.5 + 1.5 : Math.random() * 2.2 + 0.6,
    speedX: isBurst ? Math.random() * 7 - 3.5 : Math.random() * 1.2 - 0.6,
    speedY: isBurst ? Math.random() * -5 - 2 : Math.random() * 0.8 - 0.3,
    opacity: isBurst ? 1 : Math.random() * 0.45 + 0.15,
    life: isBurst ? 120 : 180,
    color: isBurst
      ? ['#22d3ee', '#67e8f9', '#a5f3fc', '#4ade80'][Math.floor(Math.random() * 4)]
      : '#67e8f9',
  };
}

function updateParticle(p: ParticleState): void {
  p.x += p.speedX;
  p.y += p.speedY;
  p.opacity -= 0.004;
  p.life--;
  p.speedY += 0.015;
}

function drawParticle(ctx: CanvasRenderingContext2D, p: ParticleState): void {
  ctx.save();
  ctx.globalAlpha = Math.max(0, p.opacity);
  ctx.fillStyle = p.color;
  ctx.beginPath();
  ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();
}

export default function CanvasParticles({
  isActive = false,
  className = '',
}: CanvasParticlesProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const particlesRef = useRef<ParticleState[]>([]);
  const animationRef = useRef<number>();

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d', { alpha: true });
    if (!ctx) return;

    const resizeCanvas = () => {
      canvas.width = canvas.offsetWidth;
      canvas.height = canvas.offsetHeight;
    };
    resizeCanvas();
    window.addEventListener('resize', resizeCanvas);

    const animate = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      // Continuous particles while active
      if (isActive && Math.random() < 0.45) {
        const x = Math.random() * canvas.width;
        const y = Math.random() * canvas.height * 0.65;
        particlesRef.current.push(createParticle(x, y));
      }

      // Update and draw
      for (let i = particlesRef.current.length - 1; i >= 0; i--) {
        const p = particlesRef.current[i];
        updateParticle(p);
        drawParticle(ctx, p);

        if (p.opacity <= 0 || p.life <= 0) {
          particlesRef.current.splice(i, 1);
        }
      }

      animationRef.current = requestAnimationFrame(animate);
    };

    animate();

    return () => {
      cancelAnimationFrame(animationRef.current!);
      window.removeEventListener('resize', resizeCanvas);
    };
  }, [isActive]);


  return (
    <canvas
      ref={canvasRef}
      className={`absolute inset-0 pointer-events-none z-0 ${className}`}
      style={{ mixBlendMode: 'screen' }}
    />
  );
}
