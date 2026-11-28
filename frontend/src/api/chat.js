import { apiRequest } from './client.js'
import { getAuth } from './authStorage.js'

function authToken() {
  return getAuth()?.token
}

// sessionId 가 없으면 새 대화, message 가 비어 있으면 인사말을 받는다
export function sendChatMessage(sessionId, message, signal) {
  return apiRequest('/api/chat', { method: 'POST', body: { sessionId, message }, token: authToken(), signal })
}

// 보낸 마지막 말을 없던 일로 한다: 서버가 그 말로 바꿔 둔 대화 기억(조건·일정)을 보내기 전 상태로 되돌린다
export function cancelChatMessage(sessionId) {
  return apiRequest(`/api/chat/${encodeURIComponent(sessionId)}/cancel`, { method: 'POST', token: authToken() })
}

// 답을 기다리는 동안 챗봇이 지금 하는 일: { busy, step: '날씨를 모으고 있어요' 등, elapsed }
export function getChatProgress(sessionId, signal) {
  return apiRequest(`/api/chat/${encodeURIComponent(sessionId)}/progress`, { token: authToken(), signal })
}

export function resetChat(sessionId) {
  return apiRequest(`/api/chat/${encodeURIComponent(sessionId)}`, { method: 'DELETE', token: authToken() })
}
