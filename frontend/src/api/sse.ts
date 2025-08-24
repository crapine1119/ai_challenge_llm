export type SSEHandler = {
  onStart?: (payload: any) => void
  onDelta?: (chunk: string) => void
  onEnd?: (payload: any) => void
  onError?: (message: string) => void
}

export function connectSSE(url: string, body: any, handler: SSEHandler) {
  const full = new URL(url, (import.meta.env.VITE_API_BASE_URL as string) || 'http://localhost:8000').toString()
  const ctrl = new AbortController()

  // SSE with fetch (text/event-stream)
  fetch(full, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal: ctrl.signal
  }).then(async (res) => {
    if (!res.ok || !res.body) {
      handler.onError?.(`HTTP ${res.status}`)
      return
    }
    const reader = res.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''
    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })

      // SSE event parsing
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
          if (event === 'start') handler.onStart?.(payload)
          else if (event === 'delta') handler.onDelta?.(payload?.text ?? '')
          else if (event === 'end') handler.onEnd?.(payload)
          else if (event === 'error') handler.onError?.(payload?.message ?? 'error')
        } catch (e) {
          // 무시: 파싱 오류
        }
      }
    }
  }).catch((e) => handler.onError?.(String(e)))

  return () => ctrl.abort()
}
