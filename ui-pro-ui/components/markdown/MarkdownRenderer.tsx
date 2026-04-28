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
 * Détecte automatiquement si le contenu ressemble à du code et l'encadre dans un bloc markdown.
 * Cela permet d'activer le bouton de téléchargement même quand le LLM ne met pas de ```.
 */
function preprocessContent(content: string): string {
  if (!content?.trim()) return ''

  // Si le contenu contient déjà un ou plusieurs blocs de code → on ne touche à rien
  if (content.includes('```')) return content

  const trimmed = content.trim()
  const lines = trimmed.split('\n')

  // Patterns forts indiquant du code
  const strongCodePatterns = [
    /^def\s+\w+/,
    /^async def\s+/,
    /^class\s+\w+/,
    /^function\s+\w+/,
    /^const\s+\w+\s*=/,
    /^let\s+\w+\s*=/,
    /^import\s+/,
    /^from\s+\w+\s+import/,
    /^#include/,
    /^printf/,
    /^console\./,
    /^print\(/,
    /^await\s+/,
    /=>[\s{]/,
  ]

  const hasStrongCodePattern = strongCodePatterns.some((regex) =>
    lines.some((line) => regex.test(line))
  )

  // Détection plus souple
  const hasCodeLikeContent =
    trimmed.length > 80 &&
    (trimmed.includes('def ') ||
      trimmed.includes('print(') ||
      trimmed.includes('console.') ||
      trimmed.includes('function ') ||
      trimmed.includes('import ') ||
      /\{\s*\n/.test(trimmed) ||
      content.split('\n').length > 10)

  if (!hasStrongCodePattern && !hasCodeLikeContent) {
    return content
  }

  // Détection du langage
  let language = 'text'
  if (/def |print\(|import |from .* import/.test(trimmed)) language = 'python'
  else if (/function |const |let |console\.|=>/.test(trimmed)) language = 'javascript'
  else if (/class .*\{|public |private |void /.test(trimmed)) language = 'java'
  else if (/#include|std::|cout|cin/.test(trimmed)) language = 'cpp'
  else if (/<\w+.*>.*<\/\w+>/.test(trimmed)) language = 'html'

  return `\`\`\`${language}\n${trimmed}\n\`\`\``
}

const CodeComponent = ({ className, children, ...props }: any) => {
  const match = /language-(\w+)/.exec(className || '')
  const language = match?.[1] || 'text'

  // Détection du code inline
  const isInline = !match && !String(children).includes('\n')

  if (isInline) {
    return (
      <code
        className="bg-slate-800/80 px-1.5 py-0.5 rounded font-mono text-sm text-slate-200"
        {...props}
      >
        {children}
      </code>
    )
  }

  // Code block
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