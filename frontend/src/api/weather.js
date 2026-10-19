import { apiRequest } from './client.js'

export function getRegionWeather() {
  return apiRequest('/api/weather')
}

// 권역과 그 아래 도시 이름 (여행 만들기의 세부 지역 선택용, 외부 호출 없는 고정 목록)
export function getRegionCatalog() {
  return apiRequest('/api/weather/regions')
}

export function getWeatherWarnings() {
  return apiRequest('/api/weather/warnings')
}

export function getRegionAirQuality() {
  return apiRequest('/api/air-quality')
}

// 지역(시·군) 대표 사진 (앱에 사진 파일이 없는 지역만). 못 찾으면 image 가 null
export function getRegionPhoto(name, region) {
  const query = new URLSearchParams({ name, region: region ?? '' })
  return apiRequest(`/api/regions/photo?${query}`)
}
