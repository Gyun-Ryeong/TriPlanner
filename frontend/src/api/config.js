import { apiRequest } from './client.js'

export function getNaverMapClientId() {
  return apiRequest('/api/config/naver-map-client-id').then((data) => data.clientId)
}
