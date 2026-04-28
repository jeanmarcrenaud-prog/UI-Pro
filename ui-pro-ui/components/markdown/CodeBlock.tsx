// components/CodeBlock.tsx
'use client'

import { useState } from 'react'
import { Check, Copy, Download } from 'lucide-react'
import { PrismLight as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/cjs/styles/prism'
import { downloadCode } from '@/lib/download'

// Type cast to fix React 18 type incompatibility
const SyntaxHighlighterComponent = SyntaxHighlighter as React.ComponentType<{
  language?: string
  style?: object
  customStyle?: React.CSSProperties
  children: string
}>

interface CodeBlockProps {
  language?: string
  value: string
}

export function CodeBlock({ language, value }: CodeBlockProps) {
  const [copied, setCopied] = useState(false)

  const copyToClipboard = async () => {
    try {
      await navigator.clipboard.writeText(value)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (err) {
      console.error('Failed to copy:', err)
    }
  }

  const handleDownload = () => {
    downloadCode(value, language || 'txt')
  }

  return (
    <div className="relative group my-3 border border-slate-700 rounded-lg overflow-hidden bg-slate-900">
      {/* Header with language + copy + download buttons */}
      <div className="flex items-center justify-between bg-slate-800 px-4 py-2 border-b border-slate-700">
        <div className="text-xs text-slate-400 font-mono">{language || 'code'}</div>
        
        <div className="flex items-center gap-3">
          {/* Copy button */}
          <button
            onClick={copyToClipboard}
            className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-200 transition-colors"
            aria-label="Copy code"
          >
            {copied ? (
              <>
                <Check className="w-4 h-4" />
                Copied!
              </>
            ) : (
              <>
                <Copy className="w-4 h-4" />
                Copy
              </>
            )}
          </button>

          {/* Download button */}
          <button
            onClick={handleDownload}
            className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-200 transition-colors"
            aria-label="Download code"
          >
            <Download className="w-4 h-4" />
            Save
          </button>
        </div>
      </div>

      {/* Isolated code container with scrollbar */}
      <div
        className="h-64 min-h-[8rem] overflow-auto"
        style={{
          maxHeight: '16rem',
          scrollbarWidth: 'thin',
          scrollbarColor: '#475569 #1e293b'
        }}
      >
        <SyntaxHighlighterComponent
          language={language}
          style={oneDark}
          customStyle={{
            margin: 0,
            padding: '1rem',
            background: 'transparent',
            fontSize: '0.875rem',
            lineHeight: '1.5',
            minHeight: '8rem'
          }}
        >
          {value}
        </SyntaxHighlighterComponent>
      </div>
    </div>
  )
}