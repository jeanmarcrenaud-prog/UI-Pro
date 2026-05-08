// StepProgress.tsx
'use client';

import { memo, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import type { AgentStep } from '@/lib/types';
import { STEP_STATUS_LABELS, useI18n } from '@/lib/i18n';
import { useChatStore } from '@/lib/stores/chatStore';

interface StepProgressProps {
  steps: AgentStep[];
  locale?: 'en' | 'fr';
  currentStep?: number;
  showStepList?: boolean;
}

// Memoized individual step row for better list performance
const StepRow = memo(({ 
  step, 
  index, 
  activeIndex 
}: { 
  step: AgentStep; 
  index: number; 
  activeIndex: number;
}) => {
  const isActive = index === activeIndex;
  const isDone = step.status === 'done';

  return (
    <motion.div
      layout="position"
      initial={false}
      animate={{
        opacity: isDone || isActive ? 1 : 0.75,
      }}
      transition={{ duration: 0.25, ease: 'easeOut' }}
      className="flex items-center gap-2 text-xs"
    >
      <div className="w-4 flex justify-center shrink-0">
        {isDone ? (
          <motion.span
            initial={{ scale: 0.6 }}
            animate={{ scale: 1 }}
            transition={{ type: 'spring', stiffness: 500, damping: 25 }}
            className="text-emerald-400 text-base"
          >
            ✓
          </motion.span>
        ) : isActive ? (
          <motion.div
            animate={{ scale: [1, 1.3, 1] }}
            transition={{ repeat: Infinity, duration: 1.4 }}
            className="w-2.5 h-2.5 bg-violet-500 rounded-full"
          />
        ) : (
          <div className="w-2 h-2 bg-slate-600 rounded-full" />
        )}
      </div>

      <motion.span
        animate={{
          color: isActive ? '#c4b5fd' : isDone ? '#94a3b8' : '#64748b',
          textDecoration: isDone ? 'line-through' : 'none',
        }}
        className="flex-1 truncate"
      >
        {step.title}
      </motion.span>
    </motion.div>
  );
});

StepRow.displayName = 'StepRow';

export function StepProgress({
  steps = [],
  locale = 'en',
  currentStep = 0,
  showStepList = true,
}: StepProgressProps) {
  const { t } = useI18n();

  // Better store subscription - use selector directly
  const isStreaming = useChatStore((state) => state.isLoading === true);

  // Early return for no steps
  if (steps.length === 0) {
    return (
      <div className="flex gap-3 items-center">
        <div className="w-8 h-8 rounded-full bg-emerald-600 flex items-center justify-center text-xs shrink-0">
          🤖
        </div>
        <div className="bg-slate-800 text-slate-200 rounded-2xl px-4 py-3 flex-1">
          <span className="text-sm flex items-center gap-2 text-violet-400">
            ⚙️ {t.steps?.initializing ?? 'Initializing...'}
          </span>
        </div>
      </div>
    );
  }

  const doneCount = useMemo(
    () => steps.filter((s) => s.status === 'done').length,
    [steps]
  );

  const activeIndex = useMemo(() => {
    const active = steps.findIndex((s) => s.status === 'active');
    return active !== -1 ? active : Math.min(Math.max(currentStep, 0), steps.length - 1);
  }, [steps, currentStep]);

  const isComplete = doneCount === steps.length;

  // Progress calculation with streaming boost
  const progressPercentage = useMemo(() => {
    if (isComplete) return 100;

    const baseProgress = Math.round(((doneCount + 0.5) / steps.length) * 100);
    const streamingBoost = isStreaming ? [25, 25, 25, 12][doneCount] ?? 15 : 0;

    return Math.min(99, baseProgress + streamingBoost);
  }, [doneCount, steps.length, isStreaming]);

  const activeStep = steps[activeIndex];

  const getStatusLabel = useMemo(() => {
    if (!activeStep) return t.steps?.processing ?? 'Processing...';

    const key = STEP_STATUS_LABELS[activeStep.id];
    return key && t.steps?.[key as keyof typeof t.steps] 
      ? (t.steps[key as keyof typeof t.steps] as string)
      : activeStep.title || (t.steps?.processing ?? 'In progress...');
  }, [activeStep, t.steps]);

  if (isComplete) {
    return (
      <div className="flex gap-3 items-center">
        <div className="w-8 h-8 rounded-full bg-emerald-600 flex items-center justify-center text-xs shrink-0">
          🤖
        </div>
        <div className="bg-slate-800 text-emerald-400 rounded-2xl px-4 py-3 flex-1 text-sm">
          ✅ {t.steps?.complete ?? 'Task completed'}
        </div>
      </div>
    );
  }

  return (
    <div className="flex gap-3 items-start">
      <div className="w-8 h-8 rounded-full bg-emerald-600 flex items-center justify-center text-xs shrink-0">
        🤖
      </div>

      <div className="bg-slate-800 text-slate-200 rounded-2xl px-4 py-4 flex-1 space-y-4">
        {/* Header */}
        <div className="space-y-3">
          <div className="text-sm flex items-center gap-2">
            <motion.span
              animate={{ opacity: [1, 0.4, 1] }}
              transition={{ repeat: Infinity, duration: 1.8 }}
              className="inline-block w-2 h-2 bg-violet-500 rounded-full"
            />
            Step {activeIndex + 1} of {steps.length}
          </div>

          {/* Progress Bar */}
          <div className="flex items-center gap-3">
            <div className="flex-1 h-1 bg-slate-700 rounded-full overflow-hidden">
              <motion.div
                className="h-full bg-gradient-to-r from-violet-500 to-fuchsia-500 rounded-full"
                animate={{ width: `${progressPercentage}%` }}
                transition={{ duration: 0.4, ease: 'easeOut' }}
              />
            </div>
            <span className="text-xs font-mono text-slate-400 w-9 text-right">
              {progressPercentage}%
            </span>
          </div>
        </div>

        {/* Current Step Status */}
        <div className="text-xs text-slate-400 line-clamp-2">
          {getStatusLabel}
        </div>

        {/* Step List */}
        {showStepList && (
          <div className="pt-3 border-t border-slate-700">
            <div className="uppercase text-[10px] tracking-widest text-slate-500 mb-2.5">
              Progress
            </div>
            <div className="space-y-2.5">
              <AnimatePresence initial={false}>
                {steps.map((step, index) => (
                  <StepRow
                    key={step.id ?? `step-${index}`}
                    step={step}
                    index={index}
                    activeIndex={activeIndex}
                  />
                ))}
              </AnimatePresence>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

StepProgress.displayName = 'StepProgress';