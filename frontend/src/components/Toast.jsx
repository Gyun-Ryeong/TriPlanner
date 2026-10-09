import { useEffect, useRef } from 'react'
import './Toast.css'

// 화면 아래 가운데에 잠깐 떴다가 사라지는 안내 (alert 느낌).
// message: { id, text } — id 가 바뀌면 새 안내로 보고 애니메이션과 타이머를 다시 시작한다.
// onClose 는 매 렌더마다 새 함수여도 되도록 ref 로 들고 있어서, 부모가 다시 그려져도 타이머가 초기화되지 않는다.
export const TOAST_DURATION_MS = 1500

export default function Toast({ message, onClose, duration = TOAST_DURATION_MS }) {
  const onCloseRef = useRef(onClose)
  onCloseRef.current = onClose

  const id = message?.id
  useEffect(() => {
    if (id == null) return undefined
    const timer = setTimeout(() => onCloseRef.current?.(), duration)
    return () => clearTimeout(timer)
  }, [id, duration])

  if (!message) return null

  return (
    <div
      key={message.id}
      className="toast"
      role="status"
      aria-live="polite"
      style={{ animationDuration: `${duration}ms` }}
    >
      <span className="toast__icon" aria-hidden="true">✓</span>
      {message.text}
    </div>
  )
}
