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

// 화면에 보여줄 항목. 기한이 이미 지난 미완료 항목은 이제 할 필요가 없으므로(예: 출발 6일 전에 D-7 항목)
// '기한 지남'으로 탓하지 않고 목록·진행률에서 뺀다. 이미 체크한 항목은 그대로 보여준다
export function relevantItems(items) {
  return items.filter((item) => !isOverdue(item))
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

// 출발일까지 남은 일수 (오늘 출발이면 0, 이미 출발했으면 음수)
function daysUntil(startDate) {
  const [y, m, d] = startDate.split('-').map(Number)
  const start = new Date(y, m - 1, d)
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  return Math.round((start - today) / (1000 * 60 * 60 * 24))
}

// 이미 지난 기한(예: 출발이 2일 뒤인데 D-7)은 고를 수 없게 뺀다. 고를 수 있는 값이 없으면 '출발 당일'만 남긴다
export function dueOptionsFor(startDate) {
  const remaining = daysUntil(startDate)
  const options = DUE_OPTIONS.filter((days) => days <= remaining)
  return options.length > 0 ? options : [0]
}
