const STORAGE_KEY = 'triplanner_auth'
export const AUTH_CHANGED_EVENT = 'triplanner-auth-changed'

// admin 은 관리자 메뉴 표시용일 뿐이고, 관리자 권한은 서버가 요청마다 확인한다
export function saveAuth({ token, userId, email, nickname, admin = false }) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify({ token, userId, email, nickname, admin }))
  window.dispatchEvent(new Event(AUTH_CHANGED_EVENT))
}

export function getAuth() {
  const raw = localStorage.getItem(STORAGE_KEY)
  return raw ? JSON.parse(raw) : null
}

export function clearAuth() {
  localStorage.removeItem(STORAGE_KEY)
}
