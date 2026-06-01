// TodoList.tsx
// Role: Todo list component with add, toggle, delete and persistent state

'use client'

import { useState, useCallback, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

interface Todo {
  id: string
  text: string
  completed: boolean
  createdAt: number
}

const STORAGE_KEY = 'ui-pro-todos'

function loadTodos(): Todo[] {
  if (typeof window === 'undefined') return []
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : []
  } catch {
    return []
  }
}

function saveTodos(todos: Todo[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(todos))
  } catch { /* quota exceeded — silencieux */ }
}

export function TodoList() {
  const [todos, setTodos] = useState<Todo[]>(loadTodos)
  const [input, setInput] = useState('')
  const [filter, setFilter] = useState<'all' | 'active' | 'completed'>('all')
  const inputRef = useRef<HTMLInputElement>(null)

  // Persist à chaque changement
  useEffect(() => { saveTodos(todos) }, [todos])

  // Focus input au mount
  useEffect(() => { inputRef.current?.focus() }, [])

  const addTodo = useCallback(() => {
    const text = input.trim()
    if (!text) return
    const todo: Todo = {
      id: crypto.randomUUID(),
      text,
      completed: false,
      createdAt: Date.now(),
    }
    setTodos(prev => [...prev, todo])
    setInput('')
    inputRef.current?.focus()
  }, [input])

  const toggleTodo = useCallback((id: string) => {
    setTodos(prev => prev.map(t =>
      t.id === id ? { ...t, completed: !t.completed } : t
    ))
  }, [])

  const deleteTodo = useCallback((id: string) => {
    setTodos(prev => prev.filter(t => t.id !== id))
  }, [])

  const clearCompleted = useCallback(() => {
    setTodos(prev => prev.filter(t => !t.completed))
  }, [])

  const filteredTodos = todos.filter(t => {
    if (filter === 'active') return !t.completed
    if (filter === 'completed') return t.completed
    return true
  })

  const activeCount = todos.filter(t => !t.completed).length
  const completedCount = todos.length - activeCount

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') addTodo()
  }

  return (
    <div className="w-full max-w-lg mx-auto">
      {/* Header */}
      <div className="text-center mb-8">
        <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-gradient-to-br from-violet-500 to-fuchsia-600 shadow-lg shadow-violet-500/25 mb-4">
          <svg className="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
          </svg>
        </div>
        <h2 className="text-xl font-semibold text-white tracking-tight">Tasks</h2>
        <p className="text-sm text-slate-500 mt-1">
          {todos.length === 0
            ? 'No tasks yet — add one below'
            : `${activeCount} remaining${completedCount > 0 ? `, ${completedCount} done` : ''}`
          }
        </p>
      </div>

      {/* Add form */}
      <div className="flex gap-2 mb-6">
        <div className="relative flex-1">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Add a task..."
            className="w-full bg-slate-900/80 border border-slate-700 rounded-xl px-4 py-3 pr-10 text-sm text-white placeholder-slate-500 transition-colors focus:outline-none focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500"
            maxLength={200}
          />
          {input && (
            <button
              onClick={() => setInput('')}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 transition-colors"
              tabIndex={-1}
              aria-label="Clear input"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          )}
        </div>
        <button
          onClick={addTodo}
          disabled={!input.trim()}
          className="inline-flex items-center justify-center px-4 py-3 bg-violet-600 hover:bg-violet-700 active:bg-violet-800 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-medium rounded-xl transition-all hover:-translate-y-0.5 hover:shadow-lg hover:shadow-violet-500/20"
          aria-label="Add task"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
          </svg>
        </button>
      </div>

      {/* Filter tabs */}
      {todos.length > 0 && (
        <div className="flex items-center justify-between mb-4">
          <div className="flex gap-1 bg-slate-900/60 border border-slate-700/50 rounded-lg p-0.5">
            {(['all', 'active', 'completed'] as const).map(f => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`px-3 py-1.5 text-xs font-medium rounded-md transition-all ${
                  filter === f
                    ? 'bg-violet-600/20 text-violet-300 shadow-sm'
                    : 'text-slate-500 hover:text-slate-300'
                }`}
              >
                {f === 'all' ? 'All' : f === 'active' ? 'Active' : 'Done'}
              </button>
            ))}
          </div>
          {completedCount > 0 && (
            <button
              onClick={clearCompleted}
              className="text-xs text-slate-500 hover:text-red-400 transition-colors"
            >
              Clear done
            </button>
          )}
        </div>
      )}

      {/* List */}
      <div className="space-y-1.5">
        <AnimatePresence initial={false}>
          {filteredTodos.length === 0 && todos.length > 0 && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="text-center py-12 text-slate-500 text-sm"
            >
              {filter === 'active' ? 'No active tasks 🎉' : 'No completed tasks'}
            </motion.div>
          )}

          {filteredTodos.length === 0 && todos.length === 0 && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="text-center py-16"
            >
              <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-slate-800/50 mb-4">
                <svg className="w-8 h-8 text-slate-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                </svg>
              </div>
              <p className="text-slate-500 text-sm">Your task list is empty</p>
              <p className="text-slate-600 text-xs mt-1">Type something above to get started</p>
            </motion.div>
          )}

          {filteredTodos.map(todo => (
            <motion.div
              key={todo.id}
              layout
              initial={{ opacity: 0, x: -20, height: 0 }}
              animate={{ opacity: 1, x: 0, height: 'auto' }}
              exit={{ opacity: 0, x: 20, height: 0 }}
              transition={{ duration: 0.2, ease: 'easeOut' }}
              className="group flex items-center gap-3 bg-slate-900/40 border border-slate-700/40 hover:border-slate-600/60 rounded-xl px-4 py-3 transition-colors"
            >
              {/* Toggle checkbox */}
              <button
                onClick={() => toggleTodo(todo.id)}
                className={`relative w-5 h-5 rounded-lg border-2 shrink-0 flex items-center justify-center transition-all ${
                  todo.completed
                    ? 'bg-emerald-500 border-emerald-500'
                    : 'border-slate-600 hover:border-violet-400'
                }`}
                aria-label={todo.completed ? 'Mark incomplete' : 'Mark complete'}
              >
                {todo.completed && (
                  <motion.svg
                    initial={{ scale: 0 }}
                    animate={{ scale: 1 }}
                    className="w-3 h-3 text-white"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={3}
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                  </motion.svg>
                )}
              </button>

              {/* Text */}
              <span
                className={`flex-1 text-sm truncate transition-all ${
                  todo.completed
                    ? 'text-slate-500 line-through'
                    : 'text-slate-200'
                }`}
              >
                {todo.text}
              </span>

              {/* Delete button */}
              <button
                onClick={() => deleteTodo(todo.id)}
                className="opacity-0 group-hover:opacity-100 transition-opacity p-1 text-slate-600 hover:text-red-400 rounded-md hover:bg-red-500/10"
                aria-label={`Delete "${todo.text}"`}
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
              </button>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>

      {/* Footer stats */}
      {todos.length > 0 && (
        <div className="mt-6 pt-4 border-t border-slate-800 flex items-center justify-between text-xs text-slate-600">
          <span>{todos.length} total</span>
          <span>Created with ❤️</span>
        </div>
      )}
    </div>
  )
}
