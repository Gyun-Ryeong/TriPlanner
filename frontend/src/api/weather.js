import { apiRequest } from './client.js'

export function getRegionWeather() {
  return apiRequest('/api/weather')
}

export function getWeatherWarnings() {
  return apiRequest('/api/weather/warnings')
}

export function getRegionAirQuality() {
  return apiRequest('/api/air-quality')
}
