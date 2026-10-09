import { apiRequest } from './client.js'
import { getAuth } from './authStorage.js'

function authToken() {
  return getAuth()?.token
}

export function createTrip({ title, region, startDate, endDate }) {
  return apiRequest('/api/trips', {
    method: 'POST',
    body: { title, region, startDate, endDate },
    token: authToken(),
  })
}

export function getMyTrips() {
  return apiRequest('/api/trips', { token: authToken() })
}

export function deleteTrip(tripId) {
  return apiRequest(`/api/trips/${tripId}`, { method: 'DELETE', token: authToken() })
}

export function getTrip(tripId) {
  return apiRequest(`/api/trips/${tripId}`, { token: authToken() })
}

export function addTripItem(tripId, tripDayId, { placeId, itemType, visitOrder, memo }) {
  return apiRequest(`/api/trips/${tripId}/days/${tripDayId}/items`, {
    method: 'POST',
    body: { placeId, itemType, visitOrder, memo },
    token: authToken(),
  })
}

export function updateTripItem(tripId, tripDayId, itemId, { placeId, itemType, visitOrder, startTime, memo }) {
  return apiRequest(`/api/trips/${tripId}/days/${tripDayId}/items/${itemId}`, {
    method: 'PUT',
    body: { placeId, itemType, visitOrder, startTime, memo },
    token: authToken(),
  })
}

// 챗봇이 만든 일정을 새 여행으로 저장 (요청 형식은 chat/planExport.js 참고)
export function importChatPlan(request) {
  return apiRequest('/api/trips/import', { method: 'POST', body: request, token: authToken() })
}

export function deleteTripItem(tripId, tripDayId, itemId) {
  return apiRequest(`/api/trips/${tripId}/days/${tripDayId}/items/${itemId}`, {
    method: 'DELETE',
    token: authToken(),
  })
}

// 내 여행별 임박 알림 (여행 시작이 오늘 포함 3일 이내일 때 날씨·대기질·기상특보 기반 주의/위험)
export function getTripAlerts() {
  return apiRequest('/api/trips/alerts', { token: authToken() })
}

export function getDayRoute(tripId, tripDayId) {
  return apiRequest(`/api/trips/${tripId}/days/${tripDayId}/route`, { token: authToken() })
}
