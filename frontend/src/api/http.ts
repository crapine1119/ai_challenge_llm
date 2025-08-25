import axios from "axios";

// 우선순위: VITE_API_BASE_URL > define된 __API_BASE__ > 로컬 기본값
const baseURL =
  import.meta.env.VITE_API_BASE_URL ||
  (globalThis as any).__API_BASE__ ||
  "http://localhost:8000";

export const http = axios.create({
  baseURL,
  withCredentials: false,
  headers: { "Content-Type": "application/json" },
});