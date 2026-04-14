// Map language identifiers to file extensions
const LANGUAGE_EXTENSIONS: Record<string, string> = {
  js: 'js',
  ts: 'ts',
  tsx: 'tsx',
  jsx: 'jsx',
  py: 'py',
  python: 'py',
  rb: 'rb',
  ruby: 'rb',
  go: 'go',
  rs: 'rs',
  rust: 'rs',
  java: 'java',
  cpp: 'cpp',
  c: 'c',
  csharp: 'cs',
  cs: 'cs',
  php: 'php',
  swift: 'swift',
  kt: 'kt',
  kotlin: 'kt',
  scala: 'scala',
  sh: 'sh',
  bash: 'sh',
  shell: 'sh',
  sql: 'sql',
  html: 'html',
  css: 'css',
  json: 'json',
  yaml: 'yml',
  yml: 'yml',
  md: 'md',
  markdown: 'md',
  xml: 'xml',
  dockerfile: 'dockerfile',
  toml: 'toml',
}

/**
 * Extract a meaningful name from code content
 * - Looks for: class X, def X, function X, const X, let X, var X
 * - Falls back to timestamp-based name
 */
function extractNameFromCode(content: string): string {
  // Try to find a meaningful identifier from the code
  const patterns = [
    /class\s+(\w+)/,           // class MyClass
    /def\s+(\w+)/,             // def my_function
    /function\s+(\w+)/,       // function myFunction
    /const\s+(\w+)/,           // const myConst
    /let\s+(\w+)/,             // let myVar
    /var\s+(\w+)/,             // var myVar
    /interface\s+(\w+)/,      // interface MyInterface
    /type\s+(\w+)/,           // type MyType
    /pub\s+fn\s+(\w+)/,        // pub fn my_function (Rust)
    /func\s+(\w+)/,            // func myFunction
  ]

  for (const pattern of patterns) {
    const match = content.match(pattern)
    if (match && match[1]) {
      return match[1].toLowerCase()
    }
  }

  // Fallback: generate timestamp-based name
  const timestamp = new Date().toISOString().slice(0, 19).replace(/[T:]/g, '-')
  return `code-${timestamp}`
}

/**
 * Get the appropriate file extension for a language
 */
function getExtension(language: string): string {
  const lang = language.toLowerCase()
  return LANGUAGE_EXTENSIONS[lang] || 'txt'
}

export function downloadCode(content: string, language: string = 'txt') {
  // Extract meaningful name from code content
  const baseName = extractNameFromCode(content)
  const extension = getExtension(language)

  // Create filename with proper extension
  const filename = `${baseName}.${extension}`

  const blob = new Blob([content], { type: 'text/plain' })
  const url = URL.createObjectURL(blob)

  const a = document.createElement('a')
  a.href = url
  a.download = filename

  document.body.appendChild(a)
  a.click()

  setTimeout(() => {
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }, 100)
}