// src/store/analyze.ts
import { defineStore } from 'pinia'
import {
  postCompanyAnalyzeAll,
  postCompanyZeroShot,
  getStylePresetsFull,
  getLatestGeneratedStyle,
  generateJDWithDefault,
  generateJDWithGenerated
} from '@/api/backend'
import type { StylePresetItem, StyleDetail, JDGenerateParsed } from '@/api/types'

type StepStatus = 'idle' | 'running' | 'done' | 'error'

export const useAnalyzeStore = defineStore('analyze', {
  state: () => ({
    // 회사 분석
    zeroShotStatus: 'idle' as StepStatus,
    analyzeAllStatus: 'idle' as StepStatus,
    analysisLog: [] as string[],
    // 스타일
    presets: [] as StylePresetItem[],
    companyStyle: null as { id: number; style: StyleDetail } | null,
    // 사전 JD 결과
    batchStatus: 'idle' as StepStatus,
    batchLog: [] as string[],
    jdResults: [] as { label: string; markdown: string; saved_id?: number }[]
  }),
  actions: {
    log(line: string) {
      this.analysisLog.push(line)
    },
    batchLogLine(line: string) {
      this.batchLog.push(line)
    },

    async runCompanyAnalysis(params: { company_code: string; job_code: string }) {
      this.zeroShotStatus = 'running'
      this.analyzeAllStatus = 'idle'
      this.analysisLog = []
      try {
        this.log('Zero-shot 분석 시작')
        await postCompanyZeroShot({
          job_code: params.job_code,
          language: 'ko',
          provider: 'openai',
          model: 'gpt-4o',
          json_format: true
        })
        this.zeroShotStatus = 'done'
        this.log('Zero-shot 분석 완료')

        this.analyzeAllStatus = 'running'
        this.log('Few-shot + Style 분석 시작')
        await postCompanyAnalyzeAll({
          company_code: params.company_code,
          job_code: params.job_code,
          language: 'ko',
          provider: 'openai',
          model: 'gpt-4o',
          json_format: true
        })
        this.analyzeAllStatus = 'done'
        this.log('Few-shot + Style 분석 완료')
      } catch (e: any) {
        if (this.zeroShotStatus !== 'done') this.zeroShotStatus = 'error'
        else this.analyzeAllStatus = 'error'
        this.log(`오류: ${e?.message || e}`)
        throw e
      }
    },

    async loadStyles(params: { company_code: string; job_code: string }) {
      this.presets = await getStylePresetsFull()
      const latest = await getLatestGeneratedStyle(params.company_code, params.job_code)
      this.companyStyle = latest ? { id: latest.id, style: latest.style } : null
    },

    async runPreBatch(params: { company_code: string; job_code: string }) {
      this.batchStatus = 'running'
      this.batchLog = []
      this.jdResults = []
      try {
        // 기본 3종
        const baseList = ['일반적', '기술 상세', 'Notion']
        for (const name of baseList) {
          this.batchLogLine(`기본 스타일 [${name}] 생성 요청`)
          const jd = await generateJDWithDefault({
            company_code: params.company_code,
            job_code: params.job_code,
            provider: 'openai',
            model: 'gpt-4o',
            default_style_name: name,
            language: 'ko'
          })
          this.jdResults.push({ label: `기본 스타일: ${name}`, markdown: jd.markdown, saved_id: jd.saved_id })
          this.batchLogLine(`기본 스타일 [${name}] 생성 완료 (id=${jd.saved_id ?? '-'})`)
        }

        // 회사 스타일 1종
        this.batchLogLine('회사 스타일 생성 요청')
        const gen = await generateJDWithGenerated({
          company_code: params.company_code,
          job_code: params.job_code,
          provider: 'openai',
          model: 'gpt-4o',
          language: 'ko'
        })
        this.jdResults.push({ label: '회사 스타일', markdown: gen.markdown, saved_id: gen.saved_id })
        this.batchLogLine(`회사 스타일 생성 완료 (id=${gen.saved_id ?? '-'})`)

        this.batchStatus = 'done'
      } catch (e: any) {
        this.batchStatus = 'error'
        this.batchLogLine(`오류: ${e?.message || e}`)
        throw e
      }
    }
  }
})
