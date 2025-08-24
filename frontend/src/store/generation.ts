// src/store/generation.ts
import { defineStore } from 'pinia'
import { connectSSE } from '@/api/sse'
import { ENDPOINTS } from '@/api/backend'
import type { GenStatus, JDGenerateRequest } from '@/api/types'
import { useNotifications } from '@/composables/useNotifications'

export const useGenerationStore = defineStore('generation', {
  state: () => ({
    requestId: '' as string,
    status: 'idle' as GenStatus,
    content: '' as string,
    meta: {} as Record<string, any>,
    stopFn: null as null | (() => void)
  }),
  actions: {
    startGenerate(payload: JDGenerateRequest) {
      if (this.stopFn) this.stopFn()
      this.status = 'starting'
      this.content = ''
      const { notify, toast } = useNotifications()

      const run = connectSSE(ENDPOINTS.GENERATE_STREAM, payload, {
        onStart: (p) => {
          this.requestId = p?.request_id || ''
          this.meta = p || {}
          this.status = 'streaming'
        },
        onFirstToken: () => {
          // WaitHub에 있을 수 있으므로 브라우저 알림 + 토스트
          notify('초안 생성이 시작되었습니다.', { body: '지금 보러 가시겠어요?' }).catch(() => {})
          toast('초안이 준비되기 시작했어요.')
        },
        onDelta: (chunk) => {
          this.content += chunk
        },
        onEnd: (p) => {
          this.meta = { ...this.meta, ...p }
          this.status = 'done'
          notify('생성이 완료되었습니다.', { body: p?.title || 'JD 생성 완료' }).catch(() => {})
        },
        onError: (msg) => {
          this.status = 'error'
          toast(`생성 오류: ${msg}`)
        }
      })

      this.stopFn = run
      return run
    },
    stop() {
      this.stopFn?.()
      this.stopFn = null
      this.status = 'idle'
      this.requestId = ''
      this.content = ''
      this.meta = {}
    }
  }
})
