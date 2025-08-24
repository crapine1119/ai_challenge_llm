import { defineStore } from 'pinia'
import { connectSSE } from '@/api/sse'
import { ENDPOINTS } from '@/api/endpoints'

type GenStatus = 'idle' | 'starting' | 'streaming' | 'refining' | 'done' | 'error'

export const useGenerationStore = defineStore('generation', {
  state: () => ({
    requestId: '' as string,
    status: 'idle' as GenStatus,
    content: '' as string,
    meta: {} as Record<string, any>
  }),
  actions: {
    startGenerate(payload: any) {
      this.status = 'starting'
      this.content = ''
      const stop = connectSSE(ENDPOINTS.GENERATE_STREAM, payload, {
        onStart: (p) => {
          this.requestId = p?.request_id ?? ''
          this.meta = p || {}
          this.status = 'streaming'
        },
        onDelta: (chunk) => {
          this.content += chunk
        },
        onEnd: (p) => {
          this.meta = { ...this.meta, ...p }
          this.status = 'done'
        },
        onError: (msg) => {
          this.status = 'error'
          console.error('SSE error', msg)
        }
      })
      return stop
    }
  }
})
