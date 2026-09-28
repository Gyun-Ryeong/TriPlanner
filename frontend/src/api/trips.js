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

export function getTrip(tripId) {
  return apiRequest(`/api/trips/${tripId}`, { token: authToken() })
}
