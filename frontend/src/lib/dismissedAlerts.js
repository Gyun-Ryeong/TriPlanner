import { useCallback, useEffect, useMemo, useState } from 'react'

// 종 알림에서 '지운' 알림 목록. 서버에는 저장하지 않고 이 브라우저(localStorage)에만 사용자별로 보관한다
const KEY_PREFIX = 'triplanner_dismissed_alerts_'
const MAX_KEPT = 200
// 한 화면에서 지우면 종 알림 등 같은 목록을 쓰는 다른 곳도 바로 바뀌도록 알리는 이벤트
const CHANGED_EVENT = 'triplanner-dismissed-alerts-changed'

// 브라우저 저장소를 못 쓰는 환경에서는 이번 접속 동안만 지워진 것으로 둔다
const memory = new Map()

function storageKey(userId) {
  return `${KEY_PREFIX}${userId ?? 'anonymous'}`
}

function load(userId) {
  try {
    const parsed = JSON.parse(localStorage.getItem(storageKey(userId)))
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return memory.get(userId) ?? []
  }
}

function save(userId, keys) {
  memory.set(userId, keys)
  try {
    localStorage.setItem(storageKey(userId), JSON.stringify(keys))
  } catch {
    // memory 에만 남는다
  }
}

// 알림 하나를 가리키는 키. 메시지까지 포함하므로 내용(건수·수치)이 바뀌면 새 알림으로 다시 나타난다
export function weatherAlertKey(trip, alert) {
  return `W|${trip.tripId}|${alert.kind}|${alert.date ?? ''}|${alert.message}`
}

function localToday() {
  const now = new Date()
  const pad = (n) => String(n).padStart(2, '0')
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`
}

// 체크리스트 알림('오늘까지인 항목이 N개')은 항목을 체크·삭제할 때마다 N이 바뀌므로 메시지 대신 날짜로 구분한다.
// 오늘 지운 알림은 오늘 안에는 다시 뜨지 않고, 다음 날 새로 기한이 되는 항목이 있으면 다시 뜬다
export function prepAlertKey(trip, alert) {
  const detail = alert.kind === 'CHECKLIST' ? localToday() : alert.message
  return `P|${trip.tripId}|${alert.kind}|${detail}`
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
    const reload = () => setKeys(load(userId))
    reload()
    window.addEventListener(CHANGED_EVENT, reload)
    return () => window.removeEventListener(CHANGED_EVENT, reload)
  }, [userId])

  const dismiss = useCallback(
    (newKeys) => {
      const next = [...load(userId).filter((key) => !newKeys.includes(key)), ...newKeys].slice(-MAX_KEPT)
      save(userId, next)
      window.dispatchEvent(new Event(CHANGED_EVENT))
    },
    [userId],
  )

  const dismissed = useMemo(() => new Set(keys), [keys])
  return { dismissed, dismiss }
}
