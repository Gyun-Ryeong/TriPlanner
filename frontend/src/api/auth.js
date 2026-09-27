import { apiRequest } from './client.js'

export function signup({ email, password, nickname }) {
  return apiRequest('/api/auth/signup', { method: 'POST', body: { email, password, nickname } })
}

export function login({ email, password }) {
  return apiRequest('/api/auth/login', { method: 'POST', body: { email, password } })
}
