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

      {/* Isolated code container with scrollbar */}
      <div 
        className="h-64 min-h-[8rem] overflow-auto"
        style={{
          maxHeight: '16rem',
          scrollbarWidth: 'thin',
          scrollbarColor: '#475569 #1e293b'
        }}
      >
        <Highlighter
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
        </Highlighter>
      </div>
      
      {/* Code language badge */}
      <div className="absolute bottom-2 left-3 text-xs text-slate-500">
        {language || 'code'}
      </div>
    </div>
  )
}