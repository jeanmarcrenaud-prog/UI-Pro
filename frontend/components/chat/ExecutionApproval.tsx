// ExecutionApproval.tsx (chat/)
// Role: Shows the generated code with 3 action buttons after the agent finishes reviewing,
// before the code is executed. Allows the user to Execute, Correct (with feedback), or Cancel.

'use client'

import { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { chatService } from '@/services/chatService'
import { events } from '@/lib/events'

interface ApprovalState {
  stream_id: string
  code_preview: string
  message_id: string
}

export function ExecutionApproval() {
  const [approval, setApproval] = useState<ApprovalState | null>(null)
  const [feedback, setFeedback] = useState('')
  const [showFeedbackInput, setShowFeedbackInput] = useState(false)
  const feedbackRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    const unsub = events.on('awaitingApproval', (data) => {
      setApproval({
        stream_id: data.stream_id,
        code_preview: data.code_preview,
        message_id: data.message_id,
      })
    })
    return () => unsub()
  }, [])

  // Focus feedback input when it appears
  useEffect(() => {
    if (showFeedbackInput && feedbackRef.current) {
      feedbackRef.current.focus()
    }
  }, [showFeedbackInput])

  const handleExecute = () => {
    if (!approval) return
    chatService.sendExecuteDecision('execute').catch(() => {})
    setApproval(null)
    setShowFeedbackInput(false)
    setFeedback('')
  }

  const handleCorrect = () => {
    if (!showFeedbackInput) {
      setShowFeedbackInput(true)
      return
    }
    chatService.sendExecuteDecision('correct', feedback || undefined).catch(() => {})
    setApproval(null)
    setShowFeedbackInput(false)
    setFeedback('')
  }

  const handleCancel = () => {
    if (!approval) return
    chatService.sendExecuteDecision('cancel').catch(() => {})
    setApproval(null)
    setShowFeedbackInput(false)
    setFeedback('')
  }

  return (
    <AnimatePresence>
      {approval && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -10 }}
          className="w-full"
        >
          <div className="bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 border border-amber-500/30 rounded-2xl p-5 shadow-lg shadow-amber-500/10">
            {/* Header */}
            <div className="flex items-center gap-3 mb-4">
              <span className="text-xl">👀</span>
              <div>
                <div className="text-sm font-medium text-amber-300">
                  Code ready — execute or adjust?
                </div>
                <div className="text-xs text-slate-500">
                  Review the generated code before running it
                </div>
              </div>
            </div>

            {/* Code preview (truncated) */}
            {approval.code_preview && (
              <pre className="text-xs font-mono text-slate-300 bg-slate-950/80 rounded-xl p-4 mb-4 max-h-48 overflow-auto border border-slate-700/50 whitespace-pre-wrap">
                {approval.code_preview.length > 2000
                  ? approval.code_preview.slice(0, 2000) + '\n... (truncated)'
                  : approval.code_preview}
              </pre>
            )}

            {/* Feedback input (shown on "Correct" click) */}
            <AnimatePresence>
              {showFeedbackInput && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  className="mb-4"
                >
                  <textarea
                    ref={feedbackRef}
                    value={feedback}
                    onChange={(e) => setFeedback(e.target.value)}
                    placeholder="Describe what to change..."
                    className="w-full bg-slate-950/80 border border-slate-700/50 rounded-xl px-4 py-3 text-sm text-white placeholder-slate-500 outline-none focus:border-amber-500/60 transition-colors resize-none"
                    rows={3}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
                        handleCorrect()
                      }
                    }}
                  />
                  <div className="text-xs text-slate-500 mt-1">
                    Press ⌘⏎ or Ctrl⏎ to submit
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Action buttons */}
            <div className="flex flex-wrap gap-3">
              <motion.button
                onClick={handleExecute}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                className="px-6 py-2.5 bg-gradient-to-r from-emerald-600 to-emerald-500 hover:from-emerald-500 hover:to-emerald-400 rounded-xl font-semibold text-sm text-white transition-all shadow-lg shadow-emerald-500/20 flex items-center gap-2"
              >
                <span>▶</span>
                Execute
              </motion.button>

              <motion.button
                onClick={handleCorrect}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                className={`px-6 py-2.5 rounded-xl font-semibold text-sm transition-all shadow-lg flex items-center gap-2 ${
                  showFeedbackInput
                    ? 'bg-gradient-to-r from-amber-600 to-amber-500 hover:from-amber-500 hover:to-amber-400 text-white shadow-amber-500/20'
                    : 'bg-slate-800 hover:bg-slate-700 text-amber-400 border border-amber-500/30'
                }`}
              >
                <span>✏</span>
                {showFeedbackInput ? 'Send correction' : 'Correct'}
              </motion.button>

              <motion.button
                onClick={handleCancel}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                className="px-6 py-2.5 bg-slate-800 hover:bg-slate-700 rounded-xl font-semibold text-sm text-slate-400 transition-all border border-slate-700/50 flex items-center gap-2"
              >
                <span>✕</span>
                Cancel
              </motion.button>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
