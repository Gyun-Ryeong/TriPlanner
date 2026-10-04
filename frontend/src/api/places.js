import { apiRequest } from './client.js'
import { getAuth } from './authStorage.js'

function authToken() {
  return getAuth()?.token
}

export function searchPlaces(keyword) {
  return apiRequest(`/api/places/search?keyword=${encodeURIComponent(keyword)}`, { token: authToken() })
}

export function savePlace(place) {
  return apiRequest('/api/places', { method: 'POST', body: place, token: authToken() })
}
