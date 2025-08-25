// src/store/ui.ts
import { defineStore } from 'pinia'

export const useUIStore = defineStore('ui', {
  state: () => ({
    jobModalOpen: false,
    bootChecked: false, // 첫 진입 점검 1회 플래그
  }),
  actions: {
    openJobModal() { this.jobModalOpen = true },
    closeJobModal() { this.jobModalOpen = false },
    setBootChecked(v: boolean) { this.bootChecked = v },
  },
})