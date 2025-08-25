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
  // 회사/직무 라벨: company_name / job_name → name → code 순으로 폴백
  getters: {
   ready: (s) => !!(s.selectedCompany && s.selectedJob),
   companyLabel: (s) =>
     s.selectedCompany?.company_name ??
     (s.selectedCompany as any)?.name ??
     s.selectedCompany?.company_code ??
     '',
   jobLabel: (s) =>
     s.selectedJob?.job_name ??
     (s.selectedJob as any)?.name ??
     s.selectedJob?.job_code ??
     '',
   companiesForSelect: (s) =>
     s.companies.map((c) => ({
       value: c.company_code,
       label: (c as any).company_name ?? (c as any).name ?? c.company_code,
     })),
   jobsForSelect: (s) =>
     s.jobs.map((j) => ({
       value: j.job_code,
       label: (j as any).job_name ?? (j as any).name ?? j.job_code,
     })),
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
      if (c?.company_code) localStorage.setItem(LS_COMPANY, c.company_code)
      else localStorage.removeItem(LS_COMPANY)
      if (c?.company_code) this.loadJobs(c.company_code)
    },
    chooseJob(j: JobBrief | null) {
      this.selectedJob = j
      if (j?.job_code) localStorage.setItem(LS_JOB, j.job_code)
      else localStorage.removeItem(LS_JOB)
    },

    async initFromCodes(company_code?: string, job_code?: string) {
      const cc = company_code || localStorage.getItem(LS_COMPANY) || ''
      const jc = job_code || localStorage.getItem(LS_JOB) || ''

      if (!this.companies.length && !this.loadingCompanies) {
        await this.loadCompanies()
      }
     // 회사 선택
     const foundC = (cc && this.companies.find(c => c.company_code === cc)) || null
     this.selectedCompany = foundC
     this.selectedJob = null
     this.jobs = []

      // 직무 로딩 후 선택
     if (this.selectedCompany?.company_code) {
       await this.loadJobs(this.selectedCompany.company_code)
       const foundJ = (jc && this.jobs.find(j => j.job_code === jc)) || null
       this.selectedJob = foundJ
     }



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
