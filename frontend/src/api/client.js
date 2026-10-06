// 빈 값이면 현재 접속한 주소(5173)로 요청하고, Vite 프록시가 /api 를 백엔드(8080)로 전달한다
// (ngrok 등 외부 주소로 접속해도 동작하도록 localhost:8080 을 직접 부르지 않는다)
export const API_BASE_URL = ''

export async function apiRequest(path, { method = 'GET', body, token } = {}) {
  const headers = { 'Content-Type': 'application/json' }
  if (token) headers.Authorization = `Bearer ${token}`

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  })

  const contentType = response.headers.get('content-type') ?? ''
  const data = contentType.includes('application/json') ? await response.json() : null

  if (!response.ok) {
    const message = data?.message ?? data?.error ?? '요청 처리 중 오류가 발생했습니다.'
    throw new ApiError(message, response.status)
  }

  return data
}

export class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.status = status
  }
}
