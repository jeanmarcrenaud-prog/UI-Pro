import { PrismLight as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/cjs/styles/prism'
import { downloadCode } from '@/lib/download'

// Type workaround for react-syntax-highlighter
const Highlighter = SyntaxHighlighter as any

export function CodeBlock({ language, value }: any) {
  return (
    <div className="relative my-3 border border-slate-700 rounded-lg overflow-hidden">
      <button
        onClick={() => downloadCode(value, language)}
        className="absolute top-2 right-2 text-xs bg-slate-800 px-2 py-1 rounded"
      >
        💾
      </button>

      <Highlighter
        language={language}
        style={oneDark}
        customStyle={{ margin: 0 }}
      >
        {value}
      </Highlighter>
    </div>
  )
}