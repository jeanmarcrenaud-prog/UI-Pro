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
  const t = useI18n()

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
        body: JSON.stringify({ code: value, language: language })
      })
      const data = await res.json()
      
      if (data.status === 'ok') {
        setOutput(data.result)
      } else {
        setError(data.error || 'Execution failed')
      }
    } catch (err) {
      setError(String(err))
    } finally {
      setRunning(false)
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
                  <span>{t.t.codeBlock.running}</span>
                </>
              ) : (
                <>
                  <Play className="w-4 h-4" />
                  <span>{t.t.codeBlock.run}</span>
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
                <span className="text-emerald-400 font-medium">{t.t.codeBlock.copied}</span>
              </>
            ) : (
              <>
                <Copy className="w-4 h-4" />
                {t.t.codeBlock.copy}
              </>
            )}
          </button>

          {/* Download Button */}
          <button
            onClick={handleDownload}
            className="flex items-center gap-2 px-4 py-1.5 text-sm rounded-xl bg-slate-700 hover:bg-slate-600 transition-colors text-slate-200"
          >
            <Download className="w-4 h-4" />
            {t.t.codeBlock.save}
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

      {/* Output Area */}
      {(output !== null || error !== null) && (
        <div className="border-t border-slate-700 bg-slate-800 p-4">
          <div className="text-xs font-medium text-slate-400 mb-2">Output:</div>
          {error ? (
            <pre className="text-red-400 text-sm font-mono whitespace-pre-wrap">{error}</pre>
          ) : (
            <pre className="text-emerald-400 text-sm font-mono whitespace-pre-wrap">{output || '(no output)'}</pre>
          )}
        </div>
      )}
    </div>
  )
})