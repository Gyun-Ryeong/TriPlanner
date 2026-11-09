// 여행 기간 표기: 하루짜리 여행은 '0박 1일' / '1일차' 대신 '당일치기'로 보여준다

// nights: 박 수 (종료일 − 시작일)
export function durationLabel(nights) {
  return nights <= 0 ? '당일치기' : `${nights}박 ${nights + 1}일`
}

// 일차 이름: 전체가 하루뿐이면 '당일치기', 아니면 '2일차'
export function dayLabel(dayNumber, totalDays) {
  return totalDays <= 1 ? '당일치기' : `${dayNumber}일차`
}
