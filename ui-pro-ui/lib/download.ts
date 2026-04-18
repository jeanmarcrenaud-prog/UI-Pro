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
 * - Looks for: class X, def X, function X, const X, let X, var X, arrow functions
 * - Ignores matches inside comments and strings
 * - Falls back to timestamp-based name
 */
function extractNameFromCode(content: string): string {
  // Remove comments and strings to avoid false matches
  const cleaned = content
    .replace(/\/\/.*$/gm, '') // Remove single-line comments
    .replace(/\/\*[\s\S]*?\*\//g, '') // Remove multi-line comments
    .replace(/['"`].*?['"`]/gs, '""') // Replace strings with empty

  // Priority patterns (preferred declarations first)
  const patterns = [
    { regex: /class\s+(\w+)/, group: 1 },           // class MyClass
    { regex: /interface\s+(\w+)/, group: 1 },       // interface MyInterface
    { regex: /type\s+(\w+)(?:\s*[=<])/, group: 1 }, // type MyType = or type MyType<
    { regex: /function\s+(\w+)/, group: 1 },       // function myFunction
    { regex: /pub\s+fn\s+(\w+)/, group: 1 },      // pub fn my_function (Rust)
    { regex: /func\s+(\w+)/, group: 1 },         // func myFunction (Go)
    { regex: /def\s+(\w+)/, group: 1 },           // def my_function (Python)
    { regex: /const\s+(\w+)\s*[=:]/, group: 1 }, // const myConst = or const myConst:
    { regex: /let\s+(\w+)\s*[=:]/, group: 1 },    // let myVar = or let myVar:
    { regex: /var\s+(\w+)\s*[=:]/, group: 1 },     // var myVar = or var myVar:
    { regex: /=>\s*\{/, group: 0 },               // Arrow function (anonymous) - no name
    { regex: /export\s+default\s+(\w+)/, group: 1 }, // export default MyClass
    { regex: /export\s+(\w+)/, group: 1 },      // export MyFunction
  ]

  for (const { regex, group } of patterns) {
    const match = cleaned.match(regex)
    if (match && match[group] && match[group].length > 0) {
      const name = match[group].toLowerCase()
      // Validate: starts with letter, contains only word chars
      if (/^[a-zA-Z][\w]*$/.test(name)) {
        return name
      }
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
  
  // Map full language names to extensions
  const LANGUAGE_MAP: Record<string, string> = {
    'javascript': 'js',
    'typescript': 'ts',
    'python': 'py',
    'ruby': 'rb',
    'rust': 'rs',
    'go': 'go',
    'java': 'java',
    'cpp': 'cpp',
    'csharp': 'cs',
    'c#': 'cs',
    'php': 'php',
    'swift': 'swift',
    'kotlin': 'kt',
    'scala': 'scala',
    'shell': 'sh',
    'bash': 'sh',
    'sql': 'sql',
    'html': 'html',
    'css': 'css',
    'json': 'json',
    'yaml': 'yml',
    'markdown': 'md',
    'xml': 'xml',
    'dockerfile': 'dockerfile',
    'toml': 'toml',
    // Aliases
    'ts': 'ts',
    'js': 'js',
    'jsx': 'jsx',
    'tsx': 'tsx',
  }
  
  return LANGUAGE_MAP[lang] || LANGUAGE_EXTENSIONS[lang] || 'txt'
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