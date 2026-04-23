import ReactMarkdown from 'react-markdown'
import { CodeBlock } from './CodeBlock'

export function MarkdownRenderer({ content }: { content: string }) {
  return (
    <div className="code-container overflow-hidden">
      <ReactMarkdown
        components={{
          code({ className, children, node, ...props }) {
            const match = /language-(\w+)/.exec(className || '')
            const isInline = !match && !String(children).includes('\n')

            if (match) {
              return (
                <CodeBlock
                  language={match[1]}
                  value={String(children)}
                />
              )
            }

            if (isInline) {
              return <code className="bg-slate-800 px-1 rounded text-sm" {...props}>{children}</code>
            }

            // Block code (no language)
            return (
              <pre className="overflow-x-auto bg-slate-900 rounded-lg p-4 my-3 max-h-64" {...props}>
                <code className="text-sm font-mono text-slate-100">{children}</code>
              </pre>
            )
          },
          pre({ children, ...props }) {
            // Wrap all pre tags in isolated scrollable container
            return (
              <div className="bg-slate-900 rounded-lg overflow-hidden my-3 max-h-64 overflow-y-auto">
                {children}
              </div>
            )
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}