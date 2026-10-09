import { createContext, useContext } from 'react'

export const TripAlertsContext = createContext({ data: null, loading: false, error: false })

// 프로필에서 알림 설정을 바꾼 직후처럼, 페이지 이동 없이 알림을 다시 불러와야 할 때 보내는 이벤트
export const TRIP_ALERTS_REFRESH_EVENT = 'triplanner-trip-alerts-refresh'

// 서버는 단계를 코드로 내려주고, 화면에 보이는 이름은 여기서만 정한다
export const ALERT_LEVEL_LABEL = { DANGER: '주의', CAUTION: '참고' }

export function useTripAlerts() {
  return useContext(TripAlertsContext)
}

export function countAlerts(data) {
  return (data?.trips ?? []).reduce((sum, trip) => sum + trip.alerts.length, 0)
}

// 강한 단계(DANGER, 화면 이름 '주의')가 하나라도 있는지
export function hasStrongAlert(data) {
  return (data?.trips ?? []).some((trip) => trip.alerts.some((a) => a.level === 'DANGER'))
}
