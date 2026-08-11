// default-model/route.ts
// Role: Next.js API route that proxies GET requests to the backend's default model settings endpoint,
// returning fallback defaults if the backend is unavailable

import { NextResponse } from 'next/server'
import { API_CONFIG } from '@/lib/config'

// Proxy to backend FastAPI
export async function GET() {
  const backendUrl = (API_CONFIG.apiUrl || 'http://localhost:8000').replace(/\/$/, '')
  try {
    const res = await fetch(`${backendUrl}/api/settings/default-model`, {
      next: { revalidate: 0 }
    })
    if (!res.ok) throw new Error('Backend unavailable')
    const data = await res.json()
    return NextResponse.json(data)
  } catch {
    // Fallback defaults
    return NextResponse.json({
      model_fast: 'qwen3.6:latest',
      model_reasoning: 'qwen3.6:latest'
    })
  }
}