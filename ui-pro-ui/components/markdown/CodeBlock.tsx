import { PrismLight as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/cjs/styles/prism'
import { downloadCode } from '@/lib/download'

// Type workaround for react-syntax-highlighter
const Highlighter = SyntaxHighlighter as any

export function CodeBlock({ language, value }: any) {
  return (
    <div className="relative my-3 border border-slate-700 rounded-lg overflow-hidden bg-slate-900">
      <button
        onClick={() => downloadCode(value, language)}
        className="absolute top-2 right-2 text-xs bg-slate-800 px-2 py-1 rounded z-10 hover:bg-slate-700 transition-colors"
      >
        💾
      </button>

      <div className="max-h-96 overflow-y-auto">
        <Highlighter
          language={language}
          style={oneDark}
          customStyle={{ 
            margin: 0, 
            padding: '1rem',
            background: 'transparent',
            fontSize: '0.875rem',
            lineHeight: '1.5'
          }}
        >
          {value}
        </Highlighter>
      </div>
    </div>
  )
}