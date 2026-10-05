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

export function deleteTripItem(tripId, tripDayId, itemId) {
  return apiRequest(`/api/trips/${tripId}/days/${tripDayId}/items/${itemId}`, {
    method: 'DELETE',
    token: authToken(),
  })
}

export function getDayRoute(tripId, tripDayId) {
  return apiRequest(`/api/trips/${tripId}/days/${tripDayId}/route`, { token: authToken() })
}
