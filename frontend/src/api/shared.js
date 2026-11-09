import { apiRequest } from './client.js'
import { getAuth } from './authStorage.js'

function authToken() {
  return getAuth()?.token
}

// 읽기 전용 공유 링크 만들기. 이미 공유 중이면 같은 코드가 돌아온다
export function enableTripSharing(tripId) {
  return apiRequest(`/api/trips/${tripId}/share`, { method: 'POST', token: authToken() })
}

// 공유 중지. 이미 나눠 준 링크는 바로 열리지 않는다
export function disableTripSharing(tripId) {
  return apiRequest(`/api/trips/${tripId}/share`, { method: 'DELETE', token: authToken() })
}

// 공유 링크로 일정 보기 (로그인 불필요)
export function getSharedTrip(shareCode) {
  return apiRequest(`/api/shared/${encodeURIComponent(shareCode)}`)
}
