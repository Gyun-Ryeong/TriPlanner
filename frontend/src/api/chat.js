import { apiRequest } from './client.js'
import { getAuth } from './authStorage.js'

function authToken() {
  return getAuth()?.token
}

// sessionId 가 없으면 새 대화, message 가 비어 있으면 인사말을 받는다
// debug 는 관리자 계정일 때만 서버가 받아들인다 (응답에 caveats·timings·llm_stats 포함)
export function sendChatMessage(sessionId, message, debug = false) {
  return apiRequest('/api/chat', { method: 'POST', body: { sessionId, message, debug }, token: authToken() })
}

export function resetChat(sessionId) {
  return apiRequest(`/api/chat/${encodeURIComponent(sessionId)}`, { method: 'DELETE', token: authToken() })
}
