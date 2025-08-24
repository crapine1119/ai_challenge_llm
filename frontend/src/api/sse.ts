// src/api/sse.ts
import type { JDGenerateStreamStart, JDGenerateStreamEnd } from './types'

export type SSEHandler = {
  onStart?: (payload: JDGenerateStreamStart) => void
  onDelta?: (chunk: string) => void
  onEnd?: (payload: JDGenerateStreamEnd) => void
  onError?: (message: string) => void
  onFirstToken?: () => void
}

/** text/event-stream 수신용 유틸 */
export async function connectSSE(url: string, body: any, handler: SSEHandler) {
  const full = new URL(url, (import.meta.env.VITE_API_BASE_URL as string) || 'http://localhost:8000').toString()
  const ctrl = new AbortController()

  try {
    const res = await fetch(full, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: ctrl.signal
    })
    if (!res.ok || !res.body) {
      handler.onError?.(`HTTP ${res.status}`)
      return () => ctrl.abort()
    }

    const reader = res.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''
    let firstDeltaSeen = false

    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })

      const events = buffer.split('\n\n')
      buffer = events.pop() || ''

      for (const evt of events) {
        const lines = evt.split('\n')
        let event = 'message'
        let data = ''

        for (const l of lines) {
          if (l.startsWith('event:')) event = l.slice(6).trim()
          if (l.startsWith('data:')) data += l.slice(5).trim()
        }

        try {
          const payload = data ? JSON.parse(data) : null
          switch (event) {
            case 'start':
              handler.onStart?.(payload as JDGenerateStreamStart)
              break
            case 'delta':
              const text = (payload && (payload.text ?? payload.delta ?? '')) || ''
              if (text) {
                if (!firstDeltaSeen) {
                  firstDeltaSeen = true
                  handler.onFirstToken?.()
                }
                handler.onDelta?.(text)
              }
              break
            case 'end':
              handler.onEnd?.(payload as JDGenerateStreamEnd)
              break
            case 'error':
              handler.onError?.((payload && payload.message) || 'error')
              break
            default:
              break
          }
        } catch {
          /* noop */
        }
      }
    }
  } catch (e: any) {
    handler.onError?.(String(e?.message || e))
  }

  return () => ctrl.abort()
}
