import { apiRequest } from './client.js'

export function getRegionWeather() {
  return apiRequest('/api/weather')
}
