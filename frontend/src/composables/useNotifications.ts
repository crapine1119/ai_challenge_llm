// src/composables/useNotifications.ts
export function useNotifications() {
  const requestPermission = async () => {
    if (!('Notification' in window)) return false
    if (Notification.permission === 'granted') return true
    const perm = await Notification.requestPermission()
    return perm === 'granted'
  }

  const notify = async (title: string, options?: NotificationOptions) => {
    if (!('Notification' in window)) return
    if (Notification.permission !== 'granted') {
      const ok = await requestPermission()
      if (!ok) return
    }
    new Notification(title, options)
  }

  const toast = (msg: string) => {
    // 간단한 토스트: 최소 구현(필요시 UI 라이브러리로 교체)
    const el = document.createElement('div')
    el.textContent = msg
    el.style.cssText =
      'position:fixed;top:16px;right:16px;background:#111;color:#fff;padding:8px 12px;border-radius:6px;z-index:9999;opacity:0.95'
    document.body.appendChild(el)
    setTimeout(() => el.remove(), 2500)
  }

  return { requestPermission, notify, toast }
}
