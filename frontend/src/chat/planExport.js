// 챗봇(/api/chat) 응답의 일정을 '내 여행' 저장 요청(/api/trips/import) 형식으로 바꾼다.
// 장소·시간·활동 설명은 챗봇 시간표(plan[].events) 그대로 쓰고, 이동·자유 시간은 저장하지 않는다.

function cut(value, max) {
  const text = (value ?? '').toString().trim()
  return text.length > max ? text.slice(0, max) : text
}

function toCoordinate(value) {
  const number = Number(value)
  return value === '' || value == null || !Number.isFinite(number) || number === 0 ? null : number
}

// TourAPI 장소 id 가 없으면 장소로 저장할 수 없어 메모 항목이 된다
function toPlace(place) {
  if (!place?.content_id) return null
  return {
    contentId: cut(place.content_id, 50),
    name: cut(place.name, 200),
    category: cut(place.type, 50) || null,
    address: cut(place.address, 255) || null,
    latitude: toCoordinate(place.mapy),
    longitude: toCoordinate(place.mapx),
  }
}

function toItem(event) {
  if (event.kind === 'visit') {
    const place = toPlace(event.place)
    const memo = place ? event.note : [event.place?.name, event.note].filter(Boolean).join(' - ')
    return { itemType: cut(event.place?.type || '관광지', 20), startTime: event.start, memo: cut(memo, 255) || null, place }
  }
  if (event.kind === 'meal') {
    const place = toPlace(event.place)
    const label = `${event.label} 식사`
    return { itemType: cut(label, 20), startTime: event.start, memo: place ? null : label, place }
  }
  return null
}

function toDays(plan) {
  return plan.map((day) => ({ date: day.date, items: (day.events ?? []).map(toItem).filter(Boolean) }))
}

function tripTitle(name, startDate, endDate) {
  const nights = Math.round((new Date(endDate) - new Date(startDate)) / (1000 * 60 * 60 * 24))
  return nights <= 0 ? `${name} 당일 여행` : `${name} ${nights}박 ${nights + 1}일`
}

function toSavable({ name, sido, startDate, endDate, plan }) {
  const start = startDate || plan[0].date
  const end = endDate || plan[plan.length - 1].date
  return {
    label: name,
    request: { title: cut(tripTitle(name, start, end), 100), sido, startDate: start, endDate: end, days: toDays(plan) },
  }
}

// 이 답변에 저장할 수 있는 일정이 있으면 [{ label, request }] (여러 지역 일정은 지역마다 하나)
export function toSavablePlans(data) {
  // 일정이 있는 상태에서 맛집·뉴스 등을 물어봐도 응답에 기존 plan 이 실려 오므로, 일정 답변(📅 일차 제목)일 때만 저장 버튼을 단다
  if (data.stage !== 'planned' || (data.intent && data.intent !== 'plan') || !data.reply?.includes('📅')) return []

  const slots = data.slots ?? {}
  if (Array.isArray(data.plan) && data.plan.length > 0 && slots.region) {
    return [toSavable({
      name: slots.area || slots.region,
      sido: slots.region,
      startDate: slots.start_date,
      endDate: slots.end_date,
      plan: data.plan,
    })]
  }

  if (Array.isArray(data.trips)) {
    return data.trips
      .filter((trip) => Array.isArray(trip.plan) && trip.plan.length > 0 && trip.sido)
      .map((trip) => toSavable({
        name: trip.area || trip.sido,
        sido: trip.sido,
        startDate: trip.start_date,
        endDate: trip.end_date,
        plan: trip.plan,
      }))
  }
  return []
}
