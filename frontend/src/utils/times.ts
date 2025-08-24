export const fmt = (d: string | number | Date) =>
  new Date(d).toLocaleString('ko-KR', { hour12: false })
