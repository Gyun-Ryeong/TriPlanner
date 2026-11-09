import { apiRequest } from './client.js'

// 한 달치 공휴일. days 는 날짜(yyyy-MM-dd) → 이름. available=false 면 불러오지 못한 것
export function getHolidays(year, month) {
  return apiRequest(`/api/holidays?year=${year}&month=${month}`)
}
