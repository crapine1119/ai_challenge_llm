// src/store/ui.ts
import { defineStore } from 'pinia'

export const useUIStore = defineStore('ui', {
  state: () => ({
    showJobModal: false
  }),
  actions: {
    openJobModal() { this.showJobModal = true },
    closeJobModal() { this.showJobModal = false }
  }
})
