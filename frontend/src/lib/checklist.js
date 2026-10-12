// 체크리스트 항목의 기한 표시: 출발 며칠 전까지 끝낼 일인지(dueOffsetDays)를 "D-7" 같은 말로 바꾼다
export function dueBadge(dueOffsetDays) {
  return dueOffsetDays === 0 ? '출발 당일' : `D-${dueOffsetDays}`
}

function todayString() {
  const now = new Date()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  return `${now.getFullYear()}-${month}-${day}`
}

// 기한(dueDate)이 오늘보다 지났는데 아직 체크하지 않은 항목
export function isOverdue(item) {
  return !item.checked && item.dueDate < todayString()
}

export function formatDueDate(dueDate) {
  const date = new Date(dueDate)
  return `${date.getMonth() + 1}월 ${date.getDate()}일`
}

export const CATEGORY_LABELS = {
  BOOKING: '예약',
  CHECK: '확인',
  PACKING: '짐',
  DEPARTURE: '출발',
  CUSTOM: '내가 추가',
}

// 직접 추가할 때 고르는 기한 (기본 항목이 쓰는 값과 같다)
export const DUE_OPTIONS = [7, 3, 1, 0]
