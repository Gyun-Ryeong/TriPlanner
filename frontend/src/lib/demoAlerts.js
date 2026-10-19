import { prepAlertKey, weatherAlertKey } from './dismissedAlerts.js'

// 시연용 가짜 알림. 푸터의 숨김 버튼으로 켜고 끄며, 화면에서만 실제 알림에 덧붙여 보여준다 (서버·DB에는 아무것도 저장하지 않는다)
// 알림을 붙일 여행은 가장 가까운 실제 여행이고, 여행이 하나도 없을 때만 이름뿐인 가짜 여행을 쓴다
const FALLBACK_TRIP = {
  tripId: 0,
  title: '시연용 여행',
  region: '제주도',
  daysUntilStart: 1,
}

function dayLabel(date) {
  return `${date.getMonth() + 1}월 ${date.getDate()}일`
}

function demoWeatherAlerts(trip) {
  const tomorrow = new Date()
  tomorrow.setDate(tomorrow.getDate() + 1)
  const day = dayLabel(tomorrow)
  const date = `${tomorrow.getFullYear()}-${String(tomorrow.getMonth() + 1).padStart(2, '0')}-${String(tomorrow.getDate()).padStart(2, '0')}`
  return [
    {
      level: 'DANGER',
      kind: 'PRECIPITATION',
      date,
      message: `${day} 시간당 30mm 이상의 강한 비가 예보됐어요. 야외 일정은 실내로 바꾸는 것을 검토해 주세요.`,
    },
    {
      level: 'DANGER',
      kind: 'WARNING',
      date: null,
      message: `현재 호우주의보가 발효 중이에요 (${trip.region}). 여행 일정에 영향이 있을 수 있으니 확인해 주세요.`,
    },
    {
      level: 'CAUTION',
      kind: 'AIR',
      date,
      message: `${day} 미세먼지 '나쁨' 예보예요. 야외 활동 시 마스크를 챙기면 도움이 돼요. 일정을 바꿀지는 편한 대로 선택하세요.`,
    },
  ]
}

function demoPrepAlerts() {
  return [
    { level: 'CAUTION', kind: 'CHECKLIST', message: '오늘까지 챙길 체크리스트 항목이 3개 있어요.' },
    { level: 'CAUTION', kind: 'EMPTY_DAY', message: '2일차 일정이 아직 비어 있어요.' },
  ]
}

// 실제 알림(data, prep)에 시연 알림을 앞쪽에 붙인 결과와, 그 시연 알림의 지우기 키(keys)를 돌려준다
export function withDemoAlerts(data, prep) {
  const base = data ?? { alertsEnabled: true, trips: [], unavailableSources: [] }
  const trip = base.trips[0] ?? FALLBACK_TRIP

  const weather = demoWeatherAlerts(trip)
  const prepAlerts = demoPrepAlerts()

  const demoTrip = { ...trip, forecastAvailable: true, alerts: [...weather, ...(trip.alerts ?? [])] }
  const prepBase = prep ?? { alertsEnabled: true, trips: [] }
  const prepTrip = prepBase.trips.find((t) => t.tripId === trip.tripId)

  return {
    data: { ...base, alertsEnabled: true, trips: [demoTrip, ...base.trips.filter((t) => t.tripId !== trip.tripId)] },
    prep: {
      ...prepBase,
      alertsEnabled: true,
      trips: [
        { ...(prepTrip ?? trip), alerts: [...prepAlerts, ...(prepTrip?.alerts ?? [])] },
        ...prepBase.trips.filter((t) => t.tripId !== trip.tripId),
      ],
    },
    keys: [...weather.map((a) => weatherAlertKey(trip, a)), ...prepAlerts.map((a) => prepAlertKey(trip, a))],
  }
}
