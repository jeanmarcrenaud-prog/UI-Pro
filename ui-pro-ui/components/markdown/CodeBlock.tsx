// components/CodeBlock.tsx
'use client'

import { useState, memo } from 'react'
import { Check, Copy, Download } from 'lucide-react'
import { PrismLight as SyntaxHighlighter } from 'react-syntax-highlighter'
import { vscDarkPlus } from 'react-syntax-highlighter/dist/cjs/styles/prism'

import { downloadCode } from '@/lib/download'

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

  const displayLanguage = language.toUpperCase()

  return (
    <div className="relative my-5 rounded-2xl overflow-hidden border border-slate-700 bg-slate-900 shadow-xl">
      {/* Header */}
      <div className="flex items-center justify-between bg-slate-800 px-5 py-3 border-b border-slate-700">
        <div className="text-sm font-medium text-slate-300 tracking-wide">
          {displayLanguage}
        </div>

        <div className="flex items-center gap-2">
          {/* Copy Button */}
          <button
            onClick={copyToClipboard}
            className="flex items-center gap-2 px-4 py-1.5 text-sm rounded-xl bg-slate-700 hover:bg-slate-600 transition-colors text-slate-200"
          >
            {copied ? (
              <>
                <Check className="w-4 h-4 text-emerald-400" />
                <span className="text-emerald-400 font-medium">Copied</span>
              </>
            ) : (
              <>
                <Copy className="w-4 h-4" />
                Copy
              </>
            )}
          </button>

          {/* Download Button */}
          <button
            onClick={handleDownload}
            className="flex items-center gap-2 px-4 py-1.5 text-sm rounded-xl bg-slate-700 hover:bg-slate-600 transition-colors text-slate-200"
          >
            <Download className="w-4 h-4" />
            Save
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
    </div>
  )
})