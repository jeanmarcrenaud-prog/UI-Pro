// components/CodeBlock.tsx
'use client'

import { useState, memo } from 'react'
import { Check, Copy, Download, Play, Loader2 } from 'lucide-react'
import { PrismLight as SyntaxHighlighter } from 'react-syntax-highlighter'
import { vscDarkPlus } from 'react-syntax-highlighter/dist/cjs/styles/prism'

import { downloadCode } from '@/lib/download'
import { useI18n } from '@/lib/i18n'

interface CodeBlockProps {
  language?: string
  value: string
}

const SyntaxHighlighterComp = SyntaxHighlighter as React.ComponentType<any>

export const CodeBlock = memo(function CodeBlock({ 
  language = 'text', 
  value = '' 
}: CodeBlockProps) {
  const [copied, setCopied] = useState(false)
  const [running, setRunning] = useState(false)
  const [output, setOutput] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [showParams, setShowParams] = useState(false)
  const [params, setParams] = useState('')
  const [validating, setValidating] = useState(false)
  const [validationResult, setValidationResult] = useState<{errors: string[]; warnings: string[]} | null>(null)
  const { t } = useI18n()

  const copyToClipboard = async () => {
    if (!value) return
    try {
      await navigator.clipboard.writeText(value)
      setCopied(true)
      setTimeout(() => setCopied(false), 1800)
    } catch (err) {
      console.error('Copy failed:', err)
    }
  }

  const handleDownload = () => {
    if (!value) return
    downloadCode(value, language)
  }

  const handleRun = async () => {
    if (!value || language !== 'python') return
    
    setRunning(true)
    setOutput(null)
    setError(null)
    
    try {
      const res = await fetch('http://localhost:8000/api/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          code: value, 
          language: language,
          args: params || undefined,
          validate: true  // Enable error detection
        })
      })
      const data = await res.json()
      
      if (data.status === 'ok') {
        setOutput(data.result)
        // Check for errors/warnings in output
        if (data.errors || data.warnings) {
          setValidationResult({ errors: data.errors || [], warnings: data.warnings || [] })
        }
      } else {
        setError(data.error || 'Execution failed')
      }
    } catch (err) {
      setError(String(err))
    } finally {
      setRunning(false)
    }
  }

  // Quick validation without full execution
  const handleValidate = async () => {
    if (!value || language !== 'python') return
    
    setValidating(true)
    setValidationResult(null)
    
    try {
      const res = await fetch('http://localhost:8000/api/validate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code: value })
      })
      const data = await res.json()
      
      if (data.status === 'ok') {
        setValidationResult({ 
          errors: data.errors || [], 
          warnings: data.warnings || [] 
        })
      } else {
        setError(data.error || 'Validation failed')
      }
    } catch (err) {
      setError(String(err))
    } finally {
      setValidating(false)
    }
  }

  const displayLanguage = language.toUpperCase()
  const canRun = language.toLowerCase() === 'python'

  return (
    <div className="relative my-5 rounded-2xl overflow-hidden border border-slate-700 bg-slate-900 shadow-xl">
      {/* Header */}
      <div className="flex items-center justify-between bg-slate-800 px-5 py-3 border-b border-slate-700">
        <div className="text-sm font-medium text-slate-300 tracking-wide">
          {displayLanguage}
        </div>

        <div className="flex items-center gap-2">
          {/* Parameters Toggle */}
          {canRun && (
            <button
              onClick={() => setShowParams(!showParams)}
              className={`flex items-center gap-2 px-3 py-1.5 text-sm rounded-xl transition-colors ${
                showParams ? 'bg-violet-600 text-white' : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
              }`}
            >
              <span className="text-xs">⚙</span>
              <span className="text-xs">Params</span>
            </button>
          )}
          {/* Validate Button */}
          {canRun && (
            <button
              onClick={handleValidate}
              disabled={validating}
              className="flex items-center gap-2 px-3 py-1.5 text-sm rounded-xl bg-amber-600 hover:bg-amber-500 disabled:bg-slate-600 transition-colors text-white"
            >
              {validating ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <span className="text-xs">✓</span>
              )}
              <span className="text-xs">Check</span>
            </button>
          )}
          {/* Run Button */}
          {canRun && (
            <button
              onClick={handleRun}
              disabled={running}
              className="flex items-center gap-2 px-4 py-1.5 text-sm rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-600 transition-colors text-white"
            >
              {running ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>{t.codeBlock.running}</span>
                </>
              ) : (
                <>
                  <Play className="w-4 h-4" />
                  <span>{t.codeBlock.run}</span>
                </>
              )}
            </button>
          )}
          {/* Copy Button */}
          <button
            onClick={copyToClipboard}
            className="flex items-center gap-2 px-4 py-1.5 text-sm rounded-xl bg-slate-700 hover:bg-slate-600 transition-colors text-slate-200"
          >
            {copied ? (
              <>
                <Check className="w-4 h-4 text-emerald-400" />
                <span className="text-emerald-400 font-medium">{t.codeBlock.copied}</span>
              </>
            ) : (
              <>
                <Copy className="w-4 h-4" />
                {t.codeBlock.copy}
              </>
            )}
          </button>

          {/* Download Button */}
          <button
            onClick={handleDownload}
            className="flex items-center gap-2 px-4 py-1.5 text-sm rounded-xl bg-slate-700 hover:bg-slate-600 transition-colors text-slate-200"
          >
            <Download className="w-4 h-4" />
            {t.codeBlock.save}
          </button>
        </div>
      </div>

      {/* Code Area */}
      <div className="max-h-[520px] overflow-auto bg-[#0d1117]">
        <SyntaxHighlighterComp
          language={language.toLowerCase()}
          style={vscDarkPlus}
          customStyle={{
            margin: 0,
            padding: '1.5rem 1.75rem',
            background: 'transparent',
            fontSize: '0.92rem',
            lineHeight: '1.65',
          }}
          showLineNumbers={value.split('\n').length > 5}
          wrapLines={true}
        >
          {value}
        </SyntaxHighlighterComp>
      </div>

      {/* Parameters Input */}
      {showParams && canRun && (
        <div className="border-t border-slate-700 bg-slate-800/50 p-4">
          <div className="flex items-center gap-3">
            <label className="text-xs font-medium text-slate-400">Args:</label>
            <input
              type="text"
              value={params}
              onChange={(e) => setParams(e.target.value)}
              placeholder="arg1 arg2 --flag value"
              className="flex-1 bg-slate-900 border border-slate-600 rounded-lg px-3 py-1.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-violet-500"
            />
          </div>
        </div>
      )}

      {/* Output Area */}
      {(output !== null || error !== null || validationResult) && (
        <div className="border-t border-slate-700 bg-slate-800 p-4 space-y-3">
          {/* Validation Results */}
          {validationResult && (
            <div>
              <div className="text-xs font-medium text-slate-400 mb-2">Analysis:</div>
              {validationResult.errors.length > 0 && (
                <div className="bg-red-950/50 border border-red-900/50 rounded-lg p-2 mb-2">
                  <div className="text-xs font-medium text-red-400 mb-1">Errors:</div>
                  {validationResult.errors.map((err, i) => (
                    <pre key={i} className="text-red-300 text-xs font-mono whitespace-pre-wrap ml-2 max-h-40 overflow-auto">{err}</pre>
                  ))}
                </div>
              )}
              {validationResult.warnings.length > 0 && (
                <div className="bg-amber-950/50 border border-amber-900/50 rounded-lg p-2">
                  <div className="text-xs font-medium text-amber-400 mb-1">Warnings:</div>
                  {validationResult.warnings.map((warn, i) => (
                    <pre key={i} className="text-amber-300 text-xs font-mono whitespace-pre-wrap ml-2 max-h-40 overflow-auto">{warn}</pre>
                  ))}
                </div>
              )}
              {validationResult.errors.length === 0 && validationResult.warnings.length === 0 && (
                <div className="text-emerald-400 text-xs">✓ No issues found</div>
              )}
            </div>
          )}
          
          {/* Execution Output */}
          {(output !== null || error !== null) && (
            <div>
              <div className="text-xs font-medium text-slate-400 mb-2">Output:</div>
              {error ? (
                <pre className="text-red-400 text-sm font-mono whitespace-pre-wrap max-h-64 overflow-auto">{error}</pre>
              ) : (
                <pre className="text-emerald-400 text-sm font-mono whitespace-pre-wrap max-h-64 overflow-auto">{output || '(no output)'}</pre>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
})