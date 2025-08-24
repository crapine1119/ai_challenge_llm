// src/store/styles.ts
import { defineStore } from 'pinia'
import { getStylePresets, getGeneratedStyleLatest } from '@/api/backend'
import type { StylePreset, GeneratedStyle } from '@/api/types'

export const useStylesStore = defineStore('styles', {
  state: () => ({
    presets: [] as StylePreset[],
    latest: null as GeneratedStyle | null,
    loading: false
  }),
  actions: {
    async loadPresets() {
      this.loading = true
      try {
        this.presets = await getStylePresets()
      } finally {
        this.loading = false
      }
    },
    async loadLatest(company_code: string, job_code: string) {
      this.latest = await getGeneratedStyleLatest(company_code, job_code)
    }
  }
})
