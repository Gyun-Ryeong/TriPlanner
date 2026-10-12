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

// mode: 'driving'(자동차, 기본값) / 'walking'(도보)
export function getDayRoute(tripId, tripDayId, mode = 'driving') {
  return apiRequest(`/api/trips/${tripId}/days/${tripDayId}/route?mode=${encodeURIComponent(mode)}`, {
    token: authToken(),
  })
}

// 출발 전 준비 체크리스트 (여행을 처음 열 때 기간·지역·계절에 맞는 기본 항목이 만들어진다)
export function getChecklist(tripId) {
  return apiRequest(`/api/trips/${tripId}/checklist`, { token: authToken() })
}

export function addChecklistItem(tripId, { content, dueOffsetDays }) {
  return apiRequest(`/api/trips/${tripId}/checklist`, {
    method: 'POST',
    body: { content, dueOffsetDays },
    token: authToken(),
  })
}

export function setChecklistItemChecked(tripId, itemId, checked) {
  return apiRequest(`/api/trips/${tripId}/checklist/${itemId}`, {
    method: 'PUT',
    body: { checked },
    token: authToken(),
  })
}

export function deleteChecklistItem(tripId, itemId) {
  return apiRequest(`/api/trips/${tripId}/checklist/${itemId}`, { method: 'DELETE', token: authToken() })
}

// 일정 변경·준비 알림: 체크리스트 기한이 지났거나 오늘까지인 항목, 출발 7일 이내인데 비어 있는 일정
export function getPrepAlerts() {
  return apiRequest('/api/trips/prep-alerts', { token: authToken() })
}
