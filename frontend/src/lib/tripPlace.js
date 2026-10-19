// 여행지 표시 문구: 세부 지역(시)을 골랐으면 '제주도 · 서귀포', 아니면 권역 이름만
export function placeLabel(trip) {
  return trip.city ? `${trip.region} · ${trip.city}` : trip.region
}
