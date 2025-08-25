// src/store/ui.ts
import { defineStore } from 'pinia'
import type { CompanyBrief, JobBrief } from '@/api/types'

type ChangeSnapshot = {
  company_code: string
  job_code: string
}

export const useUIStore = defineStore('ui', {
  state: () => ({
    showJobModal: false,
    /** 최초 부팅 시 모달 1회 오픈 여부 표시 */
    bootChecked: false,
    /** '직무 변경'에서 반드시 다른 직무로 바꾸도록 강제할지 여부 */
    forceChange: false,
    /** 모달을 연 시점의 기존 선택 스냅샷(변경 강제 비교에 사용) */
    changeSnapshot: { company_code: '', job_code: '' } as ChangeSnapshot
  }),
  actions: {
    /** 최초 앱 부팅 체크 플래그 */
    setBootChecked(v: boolean) { this.bootChecked = v },

    /** 일반 오픈(최초 진입 등) */
    openJobModal(opts?: { requireDifferentJob?: boolean; snapshot?: ChangeSnapshot }) {
      this.forceChange = !!opts?.requireDifferentJob
      this.changeSnapshot = opts?.snapshot || { company_code: '', job_code: '' }
      this.showJobModal = true
    },
    /** 상단 헤더에서 ‘직무 변경’ 버튼으로 오픈 (반드시 다른 직무로 변경 강제) */
    openJobModalForChange(snapshot: ChangeSnapshot) {
      this.forceChange = true
      this.changeSnapshot = snapshot
      this.showJobModal = true
    },
    closeJobModal() { this.showJobModal = false }
  }
})
