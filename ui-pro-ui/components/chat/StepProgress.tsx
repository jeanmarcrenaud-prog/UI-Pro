// StepProgress.tsx
'use client';

import { memo, useMemo, useState, useEffect } from 'react';
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
  activeIndex, 
  isComplete 
}: { 
  step: AgentStep; 
  index: number; 
  activeIndex: number; 
  isComplete: boolean;
}) => {
  const isActive = index === activeIndex;
  const isDone = step.status === 'done';

  return (
    <motion.div
      layout="position"
      initial={false}
      animate={{
        opacity: isDone || isActive ? 1 : 0.75,
        y: 0,
      }}
      transition={{
        duration: 0.25,
        ease: 'easeOut',
        layout: { duration: 0.35, ease: 'easeOut' },
      }}
      className="flex items-center gap-2 text-xs overflow-hidden"
    >
      <div className="w-4 flex justify-center shrink-0">
        {isDone ? (
          <motion.span
            initial={false}
            animate={{ scale: 1 }}
            transition={{ type: 'spring', stiffness: 500, damping: 25 }}
            className="text-emerald-400 text-base leading-none will-change-transform"
          >
            ✓
          </motion.span>
        ) : isActive ? (
          <motion.span
            animate={{ scale: [1, 1.25, 1] }}
            transition={{ repeat: Infinity, duration: 1.5, ease: 'easeInOut' }}
            className="w-2.5 h-2.5 bg-violet-500 rounded-full will-change-transform"
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
        transition={{ duration: 0.2 }}
        className="flex-1 truncate"
      >
        {step.title}
      </motion.span>
    </motion.div>
  );
});

StepRow.displayName = 'StepRow';

// Note: StepProgress is NOT memoized because steps array reference doesn't change
// but content does. The child StepRow IS memoized for performance.
export function StepProgress({
  steps = [],
  locale = 'en',
  currentStep = 0,
  showStepList = true,
}: StepProgressProps) {
  const { t } = useI18n();
  
  // Detect if we're streaming via uiStore status
  const [isStreaming, setIsStreaming] = useState(false);
  
  useEffect(() => {
    // Get streaming status from chatStore
    const checkStatus = () => {
      const state = useChatStore.getState();
      setIsStreaming(state.isLoading === true);
    };
    
    checkStatus();
    const interval = setInterval(checkStatus, 500);
    return () => clearInterval(interval);
  }, []);

  // Early return for no steps
  if (steps.length === 0) {
    return (
      <div className="flex gap-3 items-center">
        <div className="w-8 h-8 rounded-full bg-emerald-600 flex items-center justify-center text-xs shrink-0">
          🤖
        </div>
        <div className="bg-slate-800 text-slate-200 rounded-2xl px-4 py-3 flex-1">
          <span className="text-sm flex items-center gap-2 text-violet-400">
            ⚙️ {t.steps.initializing ?? 'Initializing...'}
          </span>
        </div>
      </div>
    );
  }

  const isComplete = useMemo(
    () => steps.every((step) => step.status === 'done'),
    [steps]
  );

  const activeIndex = useMemo(
    () => {
      // Find the index of the active step by status
      const activeIdx = steps.findIndex((s) => s.status === 'active');
      if (activeIdx !== -1) return activeIdx;
      // Fallback to currentStep prop if no active step found
      return Math.max(0, Math.min(currentStep, steps.length - 1));
    },
    [steps, currentStep]
  );

  const activeStep = steps[activeIndex];

  const currentStepNumber = activeIndex + 1;
  const totalSteps = steps.length;

  const completedSteps = useMemo(
    () => steps.filter((step) => step.status === 'done').length,
    [steps]
  );

  // Progress: stable calculation based on done count + progress through steps
  const doneCount = steps.filter((step) => step.status === 'done').length;
  
  // Streaming boost: add incremental progress during active streaming
  // Targets: 0 done→13%, 1 done→38%, 2 done→63%, 3 done→88%
  // During streaming: +25%, +25%, +25%, +12% to reach next step
  const streamingBoost = isStreaming 
    ? [25, 25, 25, 12][doneCount] || 25
    : 0;
  
  // Calculate progress: base + streaming boost
  const progressPercentage = isComplete
    ? 100
    : Math.min(99, Math.round(((doneCount + 0.5) / totalSteps) * 100) + streamingBoost);

  const getStatusLabel = useMemo((): string => {
    if (!activeStep) return t.steps.analyzing ?? 'Processing...';

    const labelKey = STEP_STATUS_LABELS[activeStep.id];
    if (labelKey) {
      const translation = t.steps[labelKey as keyof typeof t.steps];
      if (typeof translation === 'string') return translation;
    }

    return activeStep.title || (t.steps.processing ?? 'In progress...');
  }, [activeStep, t.steps]);

  // Completed state
  if (isComplete) {
    return (
      <div className="flex gap-3 items-center">
        <div className="w-8 h-8 rounded-full bg-emerald-600 flex items-center justify-center text-xs shrink-0">
          🤖
        </div>
        <div className="bg-slate-800 text-slate-200 rounded-2xl px-4 py-3 flex-1">
          <span className="text-emerald-400 text-sm flex items-center gap-2">
            ✅ {t.steps.complete ?? 'Complete'}
          </span>
        </div>
      </div>
    );
  }

  return (
    <div className="flex gap-3 items-start">
      <div className="w-8 h-8 rounded-full bg-emerald-600 flex items-center justify-center text-xs shrink-0">
        🤖
      </div>

      <div className="bg-slate-800 text-slate-200 rounded-2xl px-4 py-4 flex-1 min-w-0 space-y-4">
        {/* Header */}
        <div className="space-y-3">
          <span className="text-sm flex items-center gap-2">
            <motion.span
              animate={{ opacity: [1, 0.6, 1] }}
              transition={{ repeat: Infinity, duration: 1.6 }}
              className="w-2 h-2 bg-violet-500 rounded-full shrink-0 will-change-opacity"
            />
            ⚙️ {typeof t.steps.stepLabel === 'function'
              ? t.steps.stepLabel(currentStepNumber, totalSteps)
              : `Step ${currentStepNumber} of ${totalSteps}`}
          </span>

          {/* Progress Bar + Percentage */}
          <div className="flex items-center gap-3">
            <div className="flex-1 h-1 bg-slate-700 rounded-full overflow-hidden">
              <motion.div
                className="h-full bg-gradient-to-r from-violet-500 to-fuchsia-500 rounded-full will-change-transform"
                initial={false}
                animate={{ width: `${progressPercentage}%` }}
                transition={{ duration: 0.4, ease: 'easeOut' }}
              />
            </div>
            <span className="text-xs font-medium text-slate-400 tabular-nums w-9 text-right shrink-0">
              {progressPercentage}%
            </span>
          </div>
        </div>

        {/* Active step status */}
        <motion.span
          initial={false}
          animate={{ opacity: 1 }}
          className="text-xs text-slate-400 line-clamp-2 break-words block"
        >
          {getStatusLabel}
        </motion.span>

        {/* Optimized Step List */}
        {showStepList && (
          <div className="pt-2 border-t border-slate-700">
            <div className="text-[10px] uppercase tracking-widest text-slate-500 mb-2">
              Steps
            </div>

            <div className="space-y-2">
              <AnimatePresence initial={false}>
                {steps.map((step, index) => (
                  <StepRow
                    key={step.id || `step-${index}`}
                    step={step}
                    index={index}
                    activeIndex={activeIndex}
                    isComplete={isComplete}
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