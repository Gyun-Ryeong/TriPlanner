function todayString() {
  const now = new Date()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  return `${now.getFullYear()}-${month}-${day}`
}

// 다가오는 여행: 아직 끝나지 않은(종료일이 오늘 이후인) 여행 중 시작일이 가장 이른 것. 진행 중인 여행도 포함한다.
// trips 는 시작일 오름차순으로 온다. 날짜가 'YYYY-MM-DD' 형식이라 문자열 비교로 충분하다.
export function pickUpcomingTrip(trips) {
  const today = todayString()
  return trips.find((trip) => trip.endDate >= today) ?? null
}
