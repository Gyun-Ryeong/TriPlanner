// 실시간 알림 화면의 날씨·대기질·특보를 권역 단위로 요약하고 내 여행지와 이어 주는 함수 모음

export const GRADE_CLASS = {
  좋음: 'alerts__grade--good',
  보통: 'alerts__grade--normal',
  나쁨: 'alerts__grade--bad',
  매우나쁨: 'alerts__grade--worst',
}

// 강수 상태로 취급하는 하늘 상태 / 강수확률이 이 값 이상이면 눈에 띄게 알려준다 (여행 알림의 참고 기준과 같다)
const RAIN_STATUSES = ['비', '비/눈', '눈', '소나기']
const RAIN_NOTICE_POP = 50

// 기상특보 지역 텍스트(전국 단위 자유 텍스트)에서 권역을 찾는 키워드 (백엔드 TripAlertService.WARNING_KEYWORDS 와 같다)
const WARNING_KEYWORDS = {
  seoul: ['서울'],
  gi: ['경기', '인천', '서해5도'],
  gangwon: ['강원'],
  chungcheong: ['충청', '충북', '충남', '대전', '세종'],
  jeolla: ['전라', '전북', '전남', '광주', '흑산도'],
  gyeongsang: ['경상', '경북', '경남', '부산', '대구', '울산', '울릉도', '독도'],
  jeju: ['제주'],
}

function mostCommon(values) {
  const counts = new Map()
  values.forEach((v) => counts.set(v, (counts.get(v) ?? 0) + 1))
  let best = null
  counts.forEach((count, value) => {
    if (best === null || count > counts.get(best)) best = value
  })
  return best
}

// 권역 카드 요약: 기온 범위 + 가장 주의할 도시 한 줄
export function summarizeRegion(cities) {
  const temps = cities.map((c) => c.temperature).filter((t) => t != null)
  const tempText =
    temps.length === 0
      ? '-'
      : Math.min(...temps) === Math.max(...temps)
        ? `${temps[0]}°`
        : `${Math.min(...temps)}~${Math.max(...temps)}°`

  const multi = cities.length > 1
  const byPopDesc = (a, b) => (b.precipitationProbability ?? -1) - (a.precipitationProbability ?? -1)
  const wet = cities.filter((c) => RAIN_STATUSES.includes(c.skyStatus)).sort(byPopDesc)
  const risky = cities
    .filter((c) => (c.precipitationProbability ?? 0) >= RAIN_NOTICE_POP)
    .sort(byPopDesc)

  let notice = null
  if (wet.length > 0) {
    const c = wet[0]
    const pop = c.precipitationProbability != null ? ` · 강수확률 ${c.precipitationProbability}%` : ''
    notice = `${multi ? `${c.cityName} ` : ''}${c.skyStatus}${pop}`
  } else if (risky.length > 0) {
    const c = risky[0]
    notice = `${multi ? `${c.cityName} ` : ''}강수확률 ${c.precipitationProbability}%`
  }

  return {
    tempText,
    sky: mostCommon(cities.map((c) => c.skyStatus)) ?? '-',
    notice,
  }
}

function localToday() {
  const now = new Date()
  return new Date(now.getFullYear(), now.getMonth(), now.getDate())
}

// 'YYYY-MM-DD' 를 그 날 0시(내 컴퓨터 시간)로 바꾼다
function parseLocalDate(value) {
  const [y, m, d] = value.split('-').map(Number)
  return new Date(y, m - 1, d)
}

// 내 여행 목록에서 아직 끝나지 않은 여행만 가까운 순으로 추려, 출발까지 남은 일수(daysUntilStart)를 붙인다
export function upcomingTripsOf(trips) {
  const today = localToday()
  return (trips ?? [])
    .filter((trip) => trip.startDate && trip.endDate && parseLocalDate(trip.endDate) >= today)
    .map((trip) => ({
      tripId: trip.tripId,
      title: trip.title,
      region: trip.region,
      city: trip.city,
      startDate: trip.startDate,
      daysUntilStart: Math.round((parseLocalDate(trip.startDate) - today) / 86400000),
    }))
    .sort((a, b) => a.startDate.localeCompare(b.startDate))
}

function compact(text) {
  return (text ?? '').replace(/\s+/g, '')
}

// 내 여행지(여행의 region·city)를 날씨 API의 권역·도시와 이어 준다. 여행은 가까운 순으로 묶는다.
// 세부 지역(시)을 고른 여행은 (권역, 도시)마다, 고르지 않은 여행은 권역마다 한 곳으로 묶는다.
// 돌려주는 값: [{ key, regionId, regionName, city, trips: [{ tripId, title, daysUntilStart }] }] — 날씨 정보가 있는 곳만.
// city 는 그 권역의 날씨에 실제로 있는 도시일 때만 채운다 (아니면 null = 권역 전체)
export function myRegionsOf(trips, weatherRegions) {
  const byKey = new Map()
  ;(trips ?? []).forEach((trip) => {
    const region = weatherRegions.find((r) => compact(r.regionName) === compact(trip.region))
    if (!region) return
    const city = trip.city && region.cities.some((c) => c.cityName === trip.city) ? trip.city : null
    const key = `${region.regionId}|${city ?? ''}`
    if (!byKey.has(key)) byKey.set(key, { key, regionId: region.regionId, regionName: region.regionName, city, trips: [] })
    byKey.get(key).trips.push({ tripId: trip.tripId, title: trip.title, daysUntilStart: trip.daysUntilStart })
  })
  return [...byKey.values()]
}

// 지금 발효 중인 기상특보 중 이 권역에 해당하는 것
export function warningsForRegion(regionId, warnings) {
  const keywords = WARNING_KEYWORDS[regionId] ?? []
  return (warnings ?? []).filter((w) => w.areas.split(/[,，]/).some((area) => keywords.some((k) => area.includes(k))))
}
