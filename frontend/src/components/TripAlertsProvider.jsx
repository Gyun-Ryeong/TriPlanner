import { useEffect, useMemo, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { getTripAlerts } from '../api/trips.js'
import { TRIP_ALERTS_REFRESH_EVENT, TripAlertsContext } from '../lib/tripAlertsContext.js'

// 예보는 계속 바뀌므로 페이지를 옮길 때와 10분마다 다시 불러온다 (서버가 짧게 캐시하므로 부담이 적다)
const REFRESH_INTERVAL_MS = 10 * 60 * 1000

export default function TripAlertsProvider({ token, children }) {
  const { pathname } = useLocation()
  const [tick, setTick] = useState(0)
  const [state, setState] = useState({ data: null, loading: Boolean(token), error: false })

  useEffect(() => {
    const refresh = () => setTick((n) => n + 1)
    const id = setInterval(refresh, REFRESH_INTERVAL_MS)
    window.addEventListener(TRIP_ALERTS_REFRESH_EVENT, refresh)
    return () => {
      clearInterval(id)
      window.removeEventListener(TRIP_ALERTS_REFRESH_EVENT, refresh)
    }
  }, [])

  useEffect(() => {
    if (!token) {
      setState({ data: null, loading: false, error: false })
      return undefined
    }

    let cancelled = false
    getTripAlerts()
      .then((data) => {
        if (!cancelled) setState({ data, loading: false, error: false })
      })
      .catch(() => {
        // 이전에 받아둔 알림은 그대로 두고 오류만 표시한다
        if (!cancelled) setState((prev) => ({ data: prev.data, loading: false, error: true }))
      })

    return () => {
      cancelled = true
    }
  }, [token, pathname, tick])

  const value = useMemo(() => state, [state])
  return <TripAlertsContext.Provider value={value}>{children}</TripAlertsContext.Provider>
}
