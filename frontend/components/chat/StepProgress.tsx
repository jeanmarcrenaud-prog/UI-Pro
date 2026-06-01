// StepProgress.tsx
'use client';

import { memo, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import type { AgentStep } from '@/lib/types';
import { STEP_STATUS_LABELS, useI18n } from '@/lib/i18n';
import { useChatStore } from '@/lib/stores/chatStore';

/** Canonical pipeline order — used for both filtering and ordering in the UI.
 *  Only these 5 steps are shown; all other events (orchestrator, fixing, completed, etc.)
 *  are either injected as badges on the relevant pipeline step or filtered out entirely. */
const PIPELINE_STEP_IDS = [
  'step-analyzing',
  'step-planning',
  'step-coding',
  'step-reviewing',
  'step-executing',
] as const;

const PIPELINE_SET = new Set(PIPELINE_STEP_IDS);

interface StepProgressProps {
  steps: AgentStep[];
  locale?: 'en' | 'fr';
  currentStep?: number;
  showStepList?: boolean;
}

type BadgeVariant = 'info' | 'warning' | 'error';

interface StepBadge {
  label: string;
  variant: BadgeVariant;
}

/** Collect contextual badges from non-pipeline steps (fixing, execution_failed, etc.) */
function collectExtraBadges(steps: AgentStep[]): Map<string, StepBadge[]> {
  const badges = new Map<string, StepBadge[]>();
  for (const s of steps) {
    if (PIPELINE_SET.has(s.id)) continue;
    if (!s.detail) continue;

    if (s.id === 'step-fixing' || s.id === 'step-execution_failed') {
      const target = 'step-coding';
      if (!badges.has(target)) badges.set(target, []);
      badges.get(target)!.push({
        label: s.detail,
        variant: s.id === 'step-execution_failed' ? 'error' : 'warning',
      });
    }
  }
  return badges;
}

const BADGE_STYLES: Record<BadgeVariant, string> = {
  info: 'text-cyan-400 bg-cyan-500/10 border-cyan-500/20',
  warning: 'text-amber-400 bg-amber-500/10 border-amber-500/20',
  error: 'text-red-400 bg-red-500/10 border-red-500/20',
};

// Memoized individual step row for better list performance
const StepRow = memo(({
  step,
  index,
  activeIndex,
  badges,
}: {
  step: AgentStep;
  index: number;
  activeIndex: number;
  badges: StepBadge[];
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
      className="flex items-start gap-2 text-xs"
    >
      <div className="w-4 flex justify-center shrink-0 mt-0.5">
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

      <div className="flex-1 min-w-0">
        <motion.span
          animate={{
            color: isActive ? '#c4b5fd' : isDone ? '#94a3b8' : '#64748b',
            textDecoration: isDone ? 'line-through' : 'none',
          }}
          className="block truncate"
        >
          {step.title}
        </motion.span>
        <div className="flex flex-wrap items-center gap-1.5 mt-0.5">
          {step.detail && (
            <motion.span
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              className="text-[10px] text-slate-500 truncate"
            >
              {isActive && '▸ '}{step.detail}
            </motion.span>
          )}
          {badges.map((badge, i) => (
            <span
              key={i}
              className={`text-[10px] px-1.5 py-0.5 rounded-full border font-medium truncate max-w-[200px] ${BADGE_STYLES[badge.variant]}`}
            >
              {badge.label}
            </span>
          ))}
        </div>
      </div>
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

  // Filter to known pipeline steps only, sorted by canonical pipeline order.
  // This makes the display immune to initialSteps ordering issues.
  const pipelineSteps = useMemo(() => {
    const byId = new Map<string, AgentStep>();
    for (const s of steps) {
      if (PIPELINE_SET.has(s.id)) byId.set(s.id, s);
    }
    return PIPELINE_STEP_IDS.map((id) => byId.get(id)).filter(Boolean) as AgentStep[];
  }, [steps]);

  // Collect contextual badges from non-pipeline steps
  const extraBadges = useMemo(() => collectExtraBadges(steps), [steps]);

  // Early return for no steps
  if (pipelineSteps.length === 0) {
    return (
      <div className="flex gap-3 items-center">
        <div className="w-10 h-10 rounded-full bg-gradient-to-br from-violet-600 to-fuchsia-600 flex items-center justify-center text-sm shrink-0 shadow-lg shadow-violet-500/30">
          <motion.span
            animate={{ scale: [1, 1.2, 1] }}
            transition={{ repeat: Infinity, duration: 2 }}
          >
            🧠
          </motion.span>
        </div>
        <div className="bg-gradient-to-r from-slate-800 to-slate-800/80 border border-violet-500/20 text-slate-200 rounded-2xl px-4 py-3 flex-1">
          <span className="text-sm flex items-center gap-2 text-violet-400 font-medium">
            <motion.span
              animate={{ opacity: [1, 0.3, 1] }}
              transition={{ repeat: Infinity, duration: 1.5 }}
              className="w-2 h-2 bg-violet-500 rounded-full"
            />
            {t.steps?.initializing ?? 'Initializing Thinking Process...'}
          </span>
        </div>
      </div>
    );
  }

  const doneCount = useMemo(
    () => pipelineSteps.filter((s) => s.status === 'done').length,
    [pipelineSteps]
  );

  const activeIndex = useMemo(() => {
    const active = pipelineSteps.findIndex((s) => s.status === 'active');
    return active !== -1 ? active : Math.min(Math.max(currentStep, 0), pipelineSteps.length - 1);
  }, [pipelineSteps, currentStep]);

  const isComplete = doneCount === pipelineSteps.length;

  // Progress calculation with streaming boost
  const progressPercentage = useMemo(() => {
    if (isComplete) return 100;

    const baseProgress = Math.round(((doneCount + 0.5) / pipelineSteps.length) * 100);
    const streamingBoost = isStreaming ? [25, 25, 25, 12, 12][doneCount] ?? 15 : 0;

    return Math.min(99, baseProgress + streamingBoost);
  }, [doneCount, pipelineSteps.length, isStreaming]);

  const activeStep = pipelineSteps[activeIndex];

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
        <div className="w-10 h-10 rounded-full bg-gradient-to-br from-emerald-500 to-emerald-600 flex items-center justify-center text-sm shrink-0 shadow-lg shadow-emerald-500/30">
          ✅
        </div>
        <div className="bg-gradient-to-r from-slate-800 to-slate-800/80 border border-emerald-500/20 text-emerald-400 rounded-2xl px-4 py-3 flex-1 text-sm font-medium">
          ✅ {t.steps?.complete ?? 'Task completed successfully'}
        </div>
      </div>
    );
  }

  return (
    <div className="flex gap-3 items-start">
      {/* Enhanced robot icon with glow */}
      <div className="relative shrink-0">
        <motion.div 
          className="w-10 h-10 rounded-full bg-gradient-to-br from-violet-600 to-fuchsia-600 flex items-center justify-center text-sm shadow-lg shadow-violet-500/30"
          animate={isStreaming ? { scale: [1, 1.05, 1] } : {}}
          transition={{ repeat: Infinity, duration: 2 }}
        >
          <motion.span
            animate={isStreaming ? { rotate: [0, 15, -15, 0] } : {}}
            transition={{ repeat: Infinity, duration: 1.5 }}
          >
            🧠
          </motion.span>
        </motion.div>
        {isStreaming && (
          <motion.div
            className="absolute inset-0 rounded-full bg-violet-500/30 blur-md"
            animate={{ opacity: [0.3, 0.6, 0.3] }}
            transition={{ repeat: Infinity, duration: 1.5 }}
          />
        )}
      </div>

      {/* Enhanced card with gradient border */}
      <div className="bg-gradient-to-br from-slate-800 to-slate-800/80 border border-violet-500/20 text-slate-200 rounded-2xl px-4 py-4 flex-1 space-y-4 shadow-lg shadow-violet-5/5">
        {/* Header with Thinking Process badge */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <div className="text-sm flex items-center gap-2">
              <motion.span
                animate={{ opacity: [1, 0.3, 1] }}
                transition={{ repeat: Infinity, duration: 1.8 }}
                className="inline-block w-2 h-2 bg-violet-500 rounded-full"
              />
              <span className="text-violet-300 font-medium">Thinking Process</span>
              <span className="text-slate-500">•</span>
              <span className="text-slate-400">Step {activeIndex + 1} of {pipelineSteps.length}</span>
            </div>
          </div>

          {/* Progress Bar with glow */}
          <div className="flex items-center gap-3">
            <div className="flex-1 h-1.5 bg-slate-700 rounded-full overflow-hidden">
              <motion.div
                className="h-full bg-gradient-to-r from-violet-500 via-fuchsia-500 to-violet-500 rounded-full"
                animate={{ width: `${progressPercentage}%` }}
                transition={{ duration: 0.4, ease: 'easeOut' }}
              />
            </div>
            <span className="text-xs font-mono text-violet-400 font-bold w-9 text-right">
              {progressPercentage}%
            </span>
          </div>
        </div>

        {/* Current Step Status - more prominent */}
        <div className="text-sm text-white bg-violet-500/10 border border-violet-500/20 rounded-lg px-3 py-2">
          <div className="flex items-center gap-2">
            <motion.span
              animate={isStreaming ? { opacity: [1, 0.7, 1] } : {}}
              transition={{ repeat: Infinity, duration: 1.5 }}
              className="flex-1 truncate"
            >
              {getStatusLabel}
            </motion.span>
            {activeStep?.detail && (
              <span className="text-[10px] font-mono text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded-full border border-amber-500/20 shrink-0">
                {activeStep.detail}
              </span>
            )}
          </div>
        </div>

        {/* Step List */}
        {showStepList && (
          <div className="pt-3 border-t border-slate-700/50">
            <div className="uppercase text-[10px] tracking-widest text-violet-400/70 mb-2.5 font-medium">
              Progress
            </div>
            <div className="space-y-2.5">
              <AnimatePresence initial={false}>
                {pipelineSteps.map((step, index) => (
                  <StepRow
                    key={step.id ?? `step-${index}`}
                    step={step}
                    index={index}
                    activeIndex={activeIndex}
                    badges={extraBadges.get(step.id) ?? []}
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