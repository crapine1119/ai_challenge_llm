// src/store/catalog.ts
import { defineStore } from 'pinia'
import { useRoute, useRouter } from 'vue-router'

type Company = { company_code: string; label: string }
type Job     = { job_code: string; label: string }

const LS_KEY = 'catalog.selected' // {company_code, company_label, job_code, job_label}

export const useCatalogStore = defineStore('catalog', {
  state: () => ({
    selectedCompany: null as Company | null,
    selectedJob: null as Job | null,
  }),
  getters: {
    companyCode: (s) => s.selectedCompany?.company_code || '',
    jobCode: (s) => s.selectedJob?.job_code || '',
    companyLabel: (s) => s.selectedCompany?.label || '',
    jobLabel: (s) => s.selectedJob?.label || '',
    canRun(): boolean { return !!(this.companyCode && this.jobCode) },
  },
  actions: {
    setSelection(c: Company | null, j: Job | null) {
      this.selectedCompany = c
      this.selectedJob = j
      // persist
      const payload = c && j ? {
        company_code: c.company_code, company_label: c.label,
        job_code: j.job_code, job_label: j.label
      } : null
      if (payload) localStorage.setItem(LS_KEY, JSON.stringify(payload))
      else localStorage.removeItem(LS_KEY)
    },

    /** 쿼리/로컬스토리지에서 복원 */
    async initFromCodes(qCompany?: string, qJob?: string) {
      const route = useRoute()
      const router = useRouter()

      // 1) 라우터 쿼리 우선
      const cc = (qCompany ?? (route.query.company_code as string)) || ''
      const jc = (qJob ?? (route.query.job_code as string)) || ''

      if (cc && jc) {
        // 라벨은 백엔드에서 불러올 수 있으면 좋지만, 우선 코드=라벨로 폴백
        this.setSelection(
          { company_code: cc, label: this.selectedCompany?.label || cc },
          { job_code: jc,     label: this.selectedJob?.label || jc },
        )
        // 쿼리 정합성 보장(없으면 푸시)
        if (!route.query.company_code || !route.query.job_code) {
          router.replace({ query: { ...route.query, company_code: cc, job_code: jc } })
        }
        return
      }

      // 2) 로컬스토리지
      const raw = localStorage.getItem(LS_KEY)
      if (raw) {
        try {
          const saved = JSON.parse(raw)
          if (saved?.company_code && saved?.job_code) {
            this.setSelection(
              { company_code: saved.company_code, label: saved.company_label || saved.company_code },
              { job_code: saved.job_code,         label: saved.job_label || saved.job_code },
            )
            // 쿼리에도 반영
            const nq = { ...route.query, company_code: saved.company_code, job_code: saved.job_code }
            router.replace({ query: nq })
            return
          }
        } catch {}
      }

      // 3) 아무 것도 없으면 초기화
      this.setSelection(null, null)
    },
  },
})
