'use client';

import { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { chatService } from '@/services/chatService';
import { events } from '@/lib/events';
import type { Message } from '@/lib/types';

export default function ChatInterface() {
  const [messages, setMessages] = useState<any[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [currentSpeed, setCurrentSpeed] = useState<number>(0);
  const [finalStats, setFinalStats] = useState<string>('');
  const [progress, setProgress] = useState(0);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const unsubMessage = chatService.onMessage((msg: Message) => {
      setMessages((prev) => {
        const last = [...prev];
        const existingIdx = last.findIndex(
          (m) => m.role === 'assistant' && m.id === msg.id
        );
        if (existingIdx >= 0) {
          last[existingIdx].content = msg.content;
          if (msg.status) last[existingIdx].status = msg.status;
        } else if (msg.content) {
          last.push({
            role: 'assistant',
            content: msg.content,
            id: msg.id,
            status: msg.status || 'streaming',
          });
        }
        return last;
      });

      if (msg.status === 'streaming') {
        setProgress((p) => Math.min(95, p + 2));
      }
      if (msg.status === 'done') {
        setIsLoading(false);
      }
      if (msg.status === 'error') {
        setIsLoading(false);
        setCurrentSpeed(0);
      }
    });

    const unsubStep = events.on(
      'agentStep',
      ({ stepId, status, content }: { stepId: string; status: string; content?: string }) => {
        if (stepId === 'progress') {
          const match = (content || status).match(/(\d+\.\d+|\d+)/);
          if (match) setCurrentSpeed(parseFloat(match[1]));
        }
        if (stepId === 'generation_stats') {
          setFinalStats(content || status);
          setCurrentSpeed(0);
          setProgress(100);
          setTimeout(() => setProgress(0), 1500);
        }
      }
    );

    const unsubStatus = events.on('status', ({ status }: { status: string }) => {
      if (status === 'idle') {
        setIsLoading(false);
        setCurrentSpeed(0);
      }
    });

    return () => {
      unsubMessage();
      unsubStep();
      unsubStatus();
    };
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading, finalStats]);

  const sendMessage = async () => {
    if (!input.trim() || isLoading) return;

    setMessages((prev) => [...prev, { role: 'user', content: input }]);
    setIsLoading(true);
    setCurrentSpeed(0);
    setFinalStats('');
    setProgress(10);

    chatService.sendMessage(input);
    setInput('');
  };

  return (
    <div className="flex flex-col h-full bg-[#0a0f1c] text-white">
      {/* Messages Area */}
      <div className="flex-1 overflow-auto p-6 space-y-6 scrollbar-thin scrollbar-thumb-slate-700">
        {messages.map((msg, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
            className={`flex ${
              msg.role === 'user' ? 'justify-end' : 'justify-start'
            }`}
          >
            <div
              className={`max-w-[85%] px-5 py-3.5 rounded-2xl text-[15px] leading-relaxed ${
                msg.role === 'user'
                  ? 'bg-gradient-to-br from-blue-600 to-blue-700 shadow-lg shadow-blue-600/20'
                  : 'bg-gradient-to-br from-gray-800/90 to-gray-900/90 border border-gray-700/50 backdrop-blur-sm'
              }`}
            >
              {msg.content}
            </div>
          </motion.div>
        ))}

        {/* Indicateur de génération en cours */}
        <AnimatePresence>
          {isLoading && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="flex flex-col items-center gap-3 py-6"
            >
              {/* Barre de progression */}
              <div className="w-80 h-1.5 bg-gray-800 rounded-full overflow-hidden shadow-lg">
                <motion.div
                  className="h-full rounded-full bg-gradient-to-r from-emerald-400 via-cyan-400 to-blue-500"
                  animate={{ width: `${progress}%` }}
                  transition={{ ease: 'easeOut', duration: 0.3 }}
                  style={{ boxShadow: '0 0 12px rgba(52, 211, 153, 0.4)' }}
                />
              </div>

              {/* Vitesse en temps réel */}
              <div className="flex items-center gap-3 text-sm font-mono">
                <div className="px-4 py-1.5 bg-gray-900/80 rounded-full border border-emerald-500/30 flex items-center gap-2 backdrop-blur-sm">
                  <span className="relative flex h-2 w-2">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
                  </span>
                  <span className="text-emerald-400 drop-shadow-[0_0_6px_rgba(52,211,153,0.5)]">
                    {currentSpeed > 0
                      ? `${currentSpeed.toFixed(1)} tok/s`
                      : 'Thinking...'}
                  </span>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Statistiques finales */}
        <AnimatePresence>
          {finalStats && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="text-center"
            >
              <div className="inline-block px-6 py-3 bg-gray-900/80 border border-amber-500/30 rounded-2xl text-amber-400 font-mono text-sm backdrop-blur-sm shadow-lg shadow-amber-500/10">
                {finalStats}
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="sticky bottom-0 p-6 border-t border-gray-800/80 bg-[#0a0f1c]">
        <div className="max-w-4xl mx-auto">
          <div className="flex gap-3">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && sendMessage()}
              disabled={isLoading}
              placeholder="Message UI-Pro..."
              className="flex-1 bg-gray-900/80 border border-gray-700/50 focus:border-blue-500/60 rounded-2xl px-6 py-4 outline-none text-lg text-white placeholder-gray-500 transition-colors backdrop-blur-sm"
            />
            <button
              onClick={sendMessage}
              disabled={isLoading || !input.trim()}
              className="px-8 py-4 bg-gradient-to-r from-emerald-500 to-cyan-500 hover:from-emerald-600 hover:to-cyan-600 disabled:opacity-40 disabled:cursor-not-allowed rounded-2xl font-semibold text-white transition-all active:scale-95 shadow-lg shadow-cyan-500/20"
            >
              Envoyer
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
