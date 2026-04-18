import { NextResponse } from 'next/server'

// Proxy to backend FastAPI
export async function GET() {
  try {
    const res = await fetch('http://localhost:8000/api/settings/default-model', {
      next: { revalidate: 0 }
    })
    if (!res.ok) throw new Error('Backend unavailable')
    const data = await res.json()
    return NextResponse.json(data)
  } catch {
    // Fallback defaults
    return NextResponse.json({
      model_fast: 'qwen3.5:0.8b',
      model_reasoning: 'qwen3.5:0.8b'
    })
  }
}