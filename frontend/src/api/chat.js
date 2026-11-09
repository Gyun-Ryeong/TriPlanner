import { apiRequest } from './client.js'
import { getAuth } from './authStorage.js'

function authToken() {
  return getAuth()?.token
}

// sessionId 가 없으면 새 대화, message 가 비어 있으면 인사말을 받는다
// debug 는 관리자 계정일 때만 서버가 받아들인다 (응답에 caveats·timings·llm_stats 포함)
export function sendChatMessage(sessionId, message, debug = false, signal) {
  return apiRequest('/api/chat', { method: 'POST', body: { sessionId, message, debug }, token: authToken(), signal })
}

// 보낸 마지막 말을 없던 일로 한다: 서버가 그 말로 바꿔 둔 대화 기억(조건·일정)을 보내기 전 상태로 되돌린다
export function cancelChatMessage(sessionId) {
  return apiRequest(`/api/chat/${encodeURIComponent(sessionId)}/cancel`, { method: 'POST', token: authToken() })
}

export function resetChat(sessionId) {
  return apiRequest(`/api/chat/${encodeURIComponent(sessionId)}`, { method: 'DELETE', token: authToken() })
}
