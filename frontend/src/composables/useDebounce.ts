// src/composables/useDebounce.ts
export function useDebounce<T extends (...args: any[]) => any>(fn: T, wait = 250) {
  let t: number | undefined
  return (...args: Parameters<T>) => {
    if (t) window.clearTimeout(t)
    // @ts-ignore
    t = window.setTimeout(() => fn(...args), wait)
  }
}
