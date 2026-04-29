// MarkdownRenderer.tsx
'use client'

import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { memo, useMemo } from 'react'
import { CodeBlock } from './CodeBlock'

interface MarkdownRendererProps {
  content: string
}

/**
 * Tries to detect if content is code and wraps it in markdown code blocks.
 */
function preprocessContent(content: string): string {
  const trimmed = content?.trim()
  if (!trimmed) return ''
  
  // Already has code blocks?
  if (trimmed.includes('```')) {
    return content
  }

  const lines = trimmed.split('\n')
  const lineCount = lines.length
  
  // Check for code patterns
  const codePatterns = [
    /^def\s+\w+/, /^async def\s+/, /^class\s+\w+/, /^function\s+\w+/,
    /^const\s+/, /^let\s+/, /^var\s+\w+/, /^import\s+/, /^from\s+\w+\s+import/,
    /^#include/, /^#!/, /^printf/, /^cout/, /^console\./, /^print\(/,
    /^System\./, /^await\s+/, /^return\s+/, /^\s*if\s*\(/,
    /^export\s+/, /^const\s+\w+\s*=/, /^let\s+\w+\s*=/,
  ]
  
  const hasCodePattern = codePatterns.some(regex => 
    lines.some(line => regex.test(line))
  )
  
  // Additional heuristics
  const hasMultipleLines = lineCount > 2
  const hasIndentation = trimmed.includes('  ')
  const looksLikeCode = hasMultipleLines && (
    hasCodePattern || 
    hasIndentation || 
    trimmed.includes('def ') ||
    trimmed.includes('print(') ||
    trimmed.includes('console.') ||
    trimmed.includes('return ')
  )
  
  // NEVER wrap if starts with prose (natural language explanation)
  const startsWithNaturalLanguage = /^Here's|^This is|^Below is|^Here is|^The following|^I'll|I will|^Let me|^To get/i.test(trimmed)
  
  if (startsWithNaturalLanguage || !looksLikeCode) {
    return content
  }
  
  // Detect language
  let language = 'text'
  const lowerTrimmed = trimmed.toLowerCase()
  
  if (/^def\s|^import\s|^from\s|^print\(|if\s__/.test(trimmed) || lowerTrimmed.includes('__name__')) {
    language = 'python'
  } else if (/^function\s|^const\s|^let\s|^console\.|^export\s|^import\s/.test(trimmed)) {
    language = 'javascript'
  } else if (/^class\s|^public\s|^private\s|^void\s|^System\./.test(trimmed)) {
    language = 'java'
  } else if (/^#include|^std::|^cout|^cin|^printf\(/.test(trimmed)) {
    language = 'cpp'
  } else if (/<[a-z]+[^>]*>.*<\/[a-z]+>/i.test(trimmed)) {
    language = 'html'
  }
  
  console.log('[MarkdownRenderer] Detected code:', language)
  return `\`\`\`${language}\n${trimmed}\n\`\`\``
}

// Code component for react-markdown
const CodeComponent = ({ className, children, ...props }: any) => {
  const match = /language-(\w+)/.exec(className || '')
  const language = match?.[1] || 'text'
  const isInline = !match && !String(children).includes('\n')

  if (isInline) {
    return (
      <code className="bg-slate-800/80 px-1.5 py-0.5 rounded font-mono text-sm text-slate-200" {...props}>
        {children}
      </code>
    )
  }

  return (
    <CodeBlock
      language={language}
      value={String(children).replace(/\n$/, '')}
    />
  )
}

const PreComponent = ({ children }: any) => (
  <div className="my-4 bg-slate-900 rounded-xl overflow-hidden border border-slate-700">
    {children}
  </div>
)

export const MarkdownRenderer = memo(function MarkdownRenderer({
  content,
}: MarkdownRendererProps) {
  const processedContent = useMemo(() => preprocessContent(content), [content])

  return (
    <div className="markdown-renderer prose prose-invert prose-slate max-w-none">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          code: CodeComponent,
          pre: PreComponent,
        }}
      >
        {processedContent}
      </ReactMarkdown>
    </div>
  )
})