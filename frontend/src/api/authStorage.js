const STORAGE_KEY = 'triplanner_auth'

export function saveAuth({ token, userId, email, nickname }) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify({ token, userId, email, nickname }))
}

export function getAuth() {
  const raw = localStorage.getItem(STORAGE_KEY)
  return raw ? JSON.parse(raw) : null
}

export function clearAuth() {
  localStorage.removeItem(STORAGE_KEY)
}
