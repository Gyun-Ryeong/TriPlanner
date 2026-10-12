import { apiRequest } from './client.js'
import { getAuth } from './authStorage.js'

export function getAdminStatus() {
  return apiRequest('/api/admin/status', { token: getAuth()?.token })
}

export function getAdminUsers() {
  return apiRequest('/api/admin/users', { token: getAuth()?.token })
}

// category 를 주면 그 분류의 최근 50건, 없으면 전체의 최근 50건 (분류별 건수는 항상 전체 기준)
export function getChatbotErrors(category) {
  const query = category ? `?category=${encodeURIComponent(category)}` : ''
  return apiRequest(`/api/admin/chatbot-errors${query}`, { token: getAuth()?.token })
}

export function clearChatbotErrors() {
  return apiRequest('/api/admin/chatbot-errors', { method: 'DELETE', token: getAuth()?.token })
}

export function restoreAdminUser(userId) {
  return apiRequest(`/api/admin/users/${userId}/restore`, { method: 'POST', token: getAuth()?.token })
}
