import { useCallback, useEffect, useState } from 'react'

// 종 알림에서 '지운' 알림 목록. 서버에는 저장하지 않고 이 브라우저(localStorage)에만 사용자별로 보관한다
const KEY_PREFIX = 'triplanner_dismissed_alerts_'
const MAX_KEPT = 200

function storageKey(userId) {
  return `${KEY_PREFIX}${userId ?? 'anonymous'}`
}

function load(userId) {
  try {
    const parsed = JSON.parse(localStorage.getItem(storageKey(userId)))
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function save(userId, keys) {
  try {
    localStorage.setItem(storageKey(userId), JSON.stringify(keys))
  } catch {
    // 저장이 막힌 환경에서는 이번 접속 동안만 지워진 것으로 둔다
  }
}

// 알림 하나를 가리키는 키. 메시지까지 포함하므로 내용(건수·수치)이 바뀌면 새 알림으로 다시 나타난다
export function weatherAlertKey(trip, alert) {
  return `W|${trip.tripId}|${alert.kind}|${alert.date ?? ''}|${alert.message}`
}

export function prepAlertKey(trip, alert) {
  return `P|${trip.tripId}|${alert.kind}|${alert.message}`
}

function filterTrips(trips, keyOf, dismissed) {
  return trips
    .map((trip) => ({ ...trip, alerts: trip.alerts.filter((alert) => !dismissed.has(keyOf(trip, alert))) }))
    .filter((trip) => trip.alerts.length > 0)
}

// 지운 알림을 뺀 위험 알림·준비 알림. 알림이 남은 여행만 돌려준다
export function withoutDismissed(data, prep, dismissed) {
  return {
    data: data ? { ...data, trips: filterTrips(data.trips, weatherAlertKey, dismissed) } : data,
    prep: prep ? { ...prep, trips: filterTrips(prep.trips, prepAlertKey, dismissed) } : prep,
  }
}

// 지금 보이는 모든 알림의 키 ('모두 지우기'용)
export function allAlertKeys(data, prep) {
  const keys = []
  data?.trips.forEach((trip) => trip.alerts.forEach((alert) => keys.push(weatherAlertKey(trip, alert))))
  prep?.trips.forEach((trip) => trip.alerts.forEach((alert) => keys.push(prepAlertKey(trip, alert))))
  return keys
}

export function useDismissedAlerts(userId) {
  const [keys, setKeys] = useState(() => load(userId))

  useEffect(() => {
    setKeys(load(userId))
  }, [userId])

  const dismiss = useCallback(
    (newKeys) => {
      setKeys((prev) => {
        const next = [...prev.filter((key) => !newKeys.includes(key)), ...newKeys].slice(-MAX_KEPT)
        save(userId, next)
        return next
      })
    },
    [userId],
  )

  return { dismissed: new Set(keys), dismiss }
}
