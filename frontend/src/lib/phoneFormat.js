// 숫자만 남기고 010-1234-5678(3-4-4) 형태로 만든다. 하이픈은 뒤에 숫자가 있을 때만 붙는다.
export function formatPhone(value) {
  const digits = value.replace(/\D/g, '').slice(0, 11)
  if (digits.length <= 3) return digits
  if (digits.length <= 7) return `${digits.slice(0, 3)}-${digits.slice(3)}`
  return `${digits.slice(0, 3)}-${digits.slice(3, 7)}-${digits.slice(7)}`
}
