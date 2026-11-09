// 축제 달력 화면의 날짜 계산 (날짜는 모두 'yyyy-MM-dd' 문자열로만 다뤄 시간대 문제를 피한다)

export const SIDO_LIST = [
  '서울', '부산', '대구', '인천', '광주', '대전', '울산', '세종',
  '경기', '강원', '충북', '충남', '전북', '전남', '경북', '경남', '제주',
]

export const WEEKDAYS = ['일', '월', '화', '수', '목', '금', '토']

const pad = (n) => String(n).padStart(2, '0')

export function toIso(year, month, day) {
  return `${year}-${pad(month)}-${pad(day)}`
}

export function todayIso() {
  const now = new Date()
  return toIso(now.getFullYear(), now.getMonth() + 1, now.getDate())
}

// 달력 칸: 앞쪽은 요일을 맞추려는 빈 칸(null), 이후는 1일부터 말일까지
export function buildCells(year, month) {
  const lead = new Date(year, month - 1, 1).getDay()
  const last = new Date(year, month, 0).getDate()
  return [
    ...Array.from({ length: lead }, () => null),
    ...Array.from({ length: last }, (_, i) => toIso(year, month, i + 1)),
  ]
}

export function shiftMonth(year, month, delta) {
  const d = new Date(year, month - 1 + delta, 1)
  return { year: d.getFullYear(), month: d.getMonth() + 1 }
}

// '2026-11-07' → '11월 7일'
export function shortDate(iso) {
  const m = /^\d{4}-(\d{2})-(\d{2})$/.exec(iso ?? '')
  return m ? `${Number(m[1])}월 ${Number(m[2])}일` : ''
}

export function periodText(start, end) {
  if (!start) return ''
  return !end || start === end ? shortDate(start) : `${shortDate(start)} ~ ${shortDate(end)}`
}

// 오늘 기준 진행 상태
export function statusOf(start, end, today = todayIso()) {
  if (end && end < today) return { label: '종료', tone: 'ended' }
  if (start && start > today) return { label: '예정', tone: 'soon' }
  return { label: '진행 중', tone: 'live' }
}
