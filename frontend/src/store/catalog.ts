// src/store/catalog.ts
import { defineStore } from 'pinia'
import { getCollectedCompanies, getCollectedJobsForCompany } from '@/api/backend'
import type { CompanyBrief, JobBrief } from '@/api/types'

const LS_COMPANY = 'selectedCompanyCode'
const LS_JOB = 'selectedJobCode'

export const useCatalogStore = defineStore('catalog', {
  state: () => ({
    companies: [] as CompanyBrief[],
    jobs: [] as JobBrief[],
    selectedCompany: null as CompanyBrief | null,
    selectedJob: null as JobBrief | null,
    loadingCompanies: false,
    loadingJobs: false,
    errorCompanies: '',
    errorJobs: ''
  }),
  getters: {
    ready: (s) => !!(s.selectedCompany && s.selectedJob),
    companyLabel: (s) => s.selectedCompany?.name || s.selectedCompany?.company_code || '',
    jobLabel:     (s) => s.selectedJob?.name || s.selectedJob?.job_code || ''
  },
  actions: {
    async loadCompanies() {
      this.loadingCompanies = true
      this.errorCompanies = ''
      try {
        const list = await getCollectedCompanies()
        this.companies = list
        if (!list.length) this.errorCompanies = '수집된 회사가 없습니다.'
      } catch (e: any) {
        this.errorCompanies = e?.message || '회사 목록을 불러오지 못했습니다.'
      } finally {
        this.loadingCompanies = false
      }
    },
    async loadJobs(company_code?: string) {
      this.loadingJobs = true
      this.errorJobs = ''
      try {
        const list = await getCollectedJobsForCompany(company_code)
        this.jobs = list
        if (!list.length) this.errorJobs = '해당 회사의 직무가 없습니다.'
      } catch (e: any) {
        this.errorJobs = e?.message || '직무 목록을 불러오지 못했습니다.'
      } finally {
        this.loadingJobs = false
      }
    },

    chooseCompany(c: CompanyBrief | null) {
      this.selectedCompany = c
      this.selectedJob = null
      this.jobs = []
      // persist
      if (c?.company_code) localStorage.setItem(LS_COMPANY, c.company_code)
      else localStorage.removeItem(LS_COMPANY)
      if (c?.company_code) this.loadJobs(c.company_code)
    },
    chooseJob(j: JobBrief | null) {
      this.selectedJob = j
      if (j?.job_code) localStorage.setItem(LS_JOB, j.job_code)
      else localStorage.removeItem(LS_JOB)
    },

    /** 페이지 진입 시 선택 복원: 라우터 쿼리 > localStorage > 그대로 */
    async initFromCodes(company_code?: string, job_code?: string) {
      const cc = company_code || localStorage.getItem(LS_COMPANY) || ''
      const jc = job_code || localStorage.getItem(LS_JOB) || ''

      if (!this.companies.length && !this.loadingCompanies) {
        await this.loadCompanies()
      }
      if (cc) {
        const foundC = this.companies.find(c => c.company_code === cc) || null
        this.selectedCompany = foundC
      }
      if (this.selectedCompany?.company_code) {
        await this.loadJobs(this.selectedCompany.company_code)
        if (jc) {
          const foundJ = this.jobs.find(j => j.job_code === jc) || null
          this.selectedJob = foundJ
        }
      }
      // 최종 퍼시스트 동기화
      if (this.selectedCompany?.company_code) localStorage.setItem(LS_COMPANY, this.selectedCompany.company_code)
      if (this.selectedJob?.job_code) localStorage.setItem(LS_JOB, this.selectedJob.job_code)
    },

    async ensureLoaded() {
      if (!this.companies.length && !this.loadingCompanies) await this.loadCompanies()
      if (this.selectedCompany && !this.jobs.length && !this.loadingJobs) {
        await this.loadJobs(this.selectedCompany.company_code)
      }
    }
  }
})
