import { apiRequest } from './client.js'
import { getAuth } from './authStorage.js'

export function getAdminStatus() {
  return apiRequest('/api/admin/status', { token: getAuth()?.token })
}

export function getAdminUsers() {
  return apiRequest('/api/admin/users', { token: getAuth()?.token })
}

export function restoreAdminUser(userId) {
  return apiRequest(`/api/admin/users/${userId}/restore`, { method: 'POST', token: getAuth()?.token })
}
