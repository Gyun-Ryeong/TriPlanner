import { useCallback, useEffect, useMemo, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { getAuth } from '../api/authStorage.js'
import { getPrepAlerts, getTripAlerts } from '../api/trips.js'
import { withDemoAlerts } from '../lib/demoAlerts.js'
import { restoreAlerts } from '../lib/dismissedAlerts.js'
import { TRIP_ALERTS_REFRESH_EVENT, TripAlertsContext } from '../lib/tripAlertsContext.js'

// 예보는 계속 바뀌므로 페이지를 옮길 때와 10분마다 다시 불러온다 (서버가 짧게 캐시하므로 부담이 적다)
const REFRESH_INTERVAL_MS = 10 * 60 * 1000

export default function TripAlertsProvider({ token, children }) {
  const { pathname } = useLocation()
  const [tick, setTick] = useState(0)
  const [state, setState] = useState({ data: null, loading: Boolean(token), error: false })
  const [prep, setPrep] = useState(null)
  const [demoOn, setDemoOn] = useState(false)

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
      setPrep(null)
      return undefined
    }

    let cancelled = false
    // 준비 알림은 위험 알림과 따로 불러온다. 실패하면 이전 값을 그대로 두고 조용히 넘어간다
    getPrepAlerts()
      .then((data) => {
        if (!cancelled) setPrep(data)
      })
      .catch(() => {})
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

  // 시연 알림은 화면에서만 덧붙이므로, 끄면 서버에서 받아 둔 실제 알림이 그대로 보인다. 새로고침하면 꺼진다
  const toggleDemo = useCallback(() => {
    if (!demoOn) restoreAlerts(getAuth()?.userId, withDemoAlerts(state.data, prep).keys)
    setDemoOn(!demoOn)
  }, [demoOn, state.data, prep])

  const value = useMemo(() => {
    const shown = demoOn ? withDemoAlerts(state.data, prep) : { data: state.data, prep }
    return { ...state, data: shown.data, prep: shown.prep, demoOn, toggleDemo }
  }, [state, prep, demoOn, toggleDemo])
  return <TripAlertsContext.Provider value={value}>{children}</TripAlertsContext.Provider>
}
