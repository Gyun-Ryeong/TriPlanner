import { useEffect, useState } from 'react'
import { getHolidays } from '../api/holidays.js'

const NONE = {}

// 그 달의 공휴일 { 'yyyy-MM-dd': 이름 }. 불러오는 중이거나 실패하면 빈 객체라 달력은 공휴일 없이 그대로 보인다
export function useHolidays(year, month) {
  const key = `${year}-${month}`
  const [loaded, setLoaded] = useState({ key: '', days: NONE })

  useEffect(() => {
    let cancelled = false
    getHolidays(year, month)
      .then((data) => !cancelled && setLoaded({ key, days: data?.days ?? NONE }))
      .catch(() => !cancelled && setLoaded({ key, days: NONE }))
    return () => {
      cancelled = true
    }
  }, [key, year, month])

  return loaded.key === key ? loaded.days : NONE
}
