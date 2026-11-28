import { apiRequest } from './client.js'
import { getAuth } from './authStorage.js'

export function getAdminUsers() {
  return apiRequest('/api/admin/users', { token: getAuth()?.token })
}

export function restoreAdminUser(userId) {
  return apiRequest(`/api/admin/users/${userId}/restore`, { method: 'POST', token: getAuth()?.token })
}
