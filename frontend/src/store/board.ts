// src/store/board.ts
import { defineStore } from 'pinia'
import { getJDList } from '@/api/backend'
import type { JDItem, JDListQuery, JDListResponse, ApiResponse } from '@/api/types'

export const useBoardStore = defineStore('board', {
  state: () => ({
    items: [] as JDItem[],
    total: 0,
    loading: false,
    error: ''
  }),
  actions: {
    async loadList(params: JDListQuery) {
      this.loading = true
      this.error = ''
      try {
        const data = (await getJDList(params)) as JDListResponse | ApiResponse<JDListResponse>
        const payload = (data as any).items ? (data as JDListResponse) : (data as ApiResponse<JDListResponse>).data!
        this.items = payload.items
        this.total = payload.total
      } catch (e: any) {
        this.error = String(e?.message || e)
      } finally {
        this.loading = false
      }
    }
  }
})
