import axios from 'axios'

const baseURL = (import.meta.env.VITE_API_BASE_URL as string) || (globalThis as any).__API_BASE__ || 'http://localhost:8000'

export const http = axios.create({
  baseURL,
  timeout: 20000
})

http.interceptors.response.use(
  (res) => res,
  (err) => {
    // 필요 시 공통 에러 토스트
    return Promise.reject(err)
  }
)
