import { apiRequest } from './client.js'

// 한 달치 축제. days 는 날짜 → 그날 축제 contentId 목록 (맨 앞이 대표). available=false 면 불러오지 못한 것
export function getFestivalMonth(sido, year, month) {
  const query = new URLSearchParams({ sido, year: String(year), month: String(month) })
  return apiRequest(`/api/festivals?${query}`)
}

// 축제 하나의 소개·프로그램·요금·링크 (달력에서 눌렀을 때만 부른다)
export function getFestivalDetail(contentId) {
  return apiRequest(`/api/festivals/${encodeURIComponent(contentId)}`)
}
