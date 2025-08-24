// src/store/dash.ts
import { defineStore } from 'pinia'
import { http } from '@/api/http'
import { ENDPOINTS } from '@/api/backend'
import type { JDPreviewProgress } from '@/api/types'

export const useDashStore = defineStore('dash', {
  state: () => ({
    preview: null as JDPreviewProgress | null,
    timer: 0 as any
  }),
  actions: {
    async fetchPreview(requestId: string) {
      const res = await http.get<JDPreviewProgress>(ENDPOINTS.DASH_PREVIEW, { params: { request_id: requestId } })
      this.preview = res.data
      return this.preview
    },
    startPolling(requestId: string, ms = 2000) {
      this.stopPolling()
      this.timer = setInterval(() => this.fetchPreview(requestId).catch(() => {}), ms)
    },
    stopPolling() {
      if (this.timer) clearInterval(this.timer)
      this.timer = 0
    }
  }
})
