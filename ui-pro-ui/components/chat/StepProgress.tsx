// StepProgress.tsx
'use client';

import { motion } from 'framer-motion';
import type { AgentStep } from '@/lib/types';
import { STEP_STATUS_LABELS, translations } from '@/lib/i18n';

interface StepProgressProps {
  steps: AgentStep[];
  locale?: 'en' | 'fr';
  currentStep?: number; // 0-based index from store
}

export function StepProgress({
  steps = [],
  locale = 'en',
  currentStep = 0,
}: StepProgressProps) {
  const t = translations[locale];

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

  const isComplete = steps.every((step) => step.status === 'done');

  // Active step calculation (currentStep is the source of truth)
  const activeIndex = Math.max(0, Math.min(currentStep, steps.length - 1));
  const activeStep = steps[activeIndex];

  const currentStepNumber = activeIndex + 1;
  const totalSteps = steps.length;

  // Progress calculation: based on how many steps are actually 'done'
  const completedSteps = steps.filter((step) => step.status === 'done').length;
  const progressPercentage = isComplete 
    ? 100 
    : Math.round((completedSteps / totalSteps) * 100);

  // Safely get the status label for the active step
  const getStatusLabel = (): string => {
    if (!activeStep) return t.steps.analyzing ?? 'Processing...';

    const labelKey = STEP_STATUS_LABELS[activeStep.id];
    if (labelKey) {
      const translation = t.steps[labelKey as keyof typeof t.steps];
      if (typeof translation === 'string') {
        return translation;
      }
    }

    return activeStep.title || (t.steps.processing ?? 'In progress...');
  };

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

  // Active progress state
  return (
    <div className="flex gap-3 items-start">
      <div className="w-8 h-8 rounded-full bg-emerald-600 flex items-center justify-center text-xs shrink-0">
        🤖
      </div>

      <div className="bg-slate-800 text-slate-200 rounded-2xl px-4 py-3 flex-1 min-w-0">
        <div className="flex flex-col gap-3">
          {/* Step Counter */}
          <div>
            <span className="text-sm flex items-center gap-2">
              <motion.span
                animate={{ opacity: [1, 0.4, 1] }}
                transition={{ repeat: Infinity, duration: 1.8, ease: 'easeInOut' }}
                className="w-2 h-2 bg-violet-500 rounded-full shrink-0"
              />
              ⚙️ {typeof t.steps.stepLabel === 'function'
                ? t.steps.stepLabel(currentStepNumber, totalSteps)
                : `Step ${currentStepNumber} of ${totalSteps}`}
            </span>
          </div>

          {/* Visual Progress Bar */}
          <div className="relative h-1 bg-slate-700 rounded-full overflow-hidden">
            <motion.div
              className="absolute top-0 left-0 h-full bg-gradient-to-r from-violet-500 to-fuchsia-500 rounded-full"
              initial={{ width: '0%' }}
              animate={{ width: `${progressPercentage}%` }}
              transition={{ duration: 0.5, ease: 'easeOut' }}
            />
          </div>

          {/* Status Label */}
          <motion.span
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
            className="text-xs text-slate-400 line-clamp-2 break-words"
          >
            {getStatusLabel()}
          </motion.span>
        </div>
      </div>
    </div>
  );
}