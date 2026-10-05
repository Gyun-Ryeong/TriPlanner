import { apiRequest } from './client.js'
import { getAuth } from './authStorage.js'

function authToken() {
  return getAuth()?.token
}

export function getProfile() {
  return apiRequest('/api/me', { token: authToken() })
}

export function updateProfile({ nickname, phone }) {
  return apiRequest('/api/me', {
    method: 'PUT',
    body: { nickname, phone },
    token: authToken(),
  })
}

export function changePassword({ currentPassword, newPassword }) {
  return apiRequest('/api/me/password', {
    method: 'PUT',
    body: { currentPassword, newPassword },
    token: authToken(),
  })
}
