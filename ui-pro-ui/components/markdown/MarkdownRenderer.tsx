import ReactMarkdown from 'react-markdown'
import { CodeBlock } from './CodeBlock'

export function MarkdownRenderer({ content }: { content: string }) {
  return (
    <ReactMarkdown
      components={{
        code({ className, children }) {
          const match = /language-(\w+)/.exec(className || '')

          if (match) {
            return (
              <CodeBlock
                language={match[1]}
                value={String(children)}
              />
            )
          }

          return <code className="bg-slate-800 px-1 rounded">{children}</code>
        },
      }}
    >
      {content}
    </ReactMarkdown>
  )
}