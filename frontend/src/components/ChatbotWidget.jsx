import { useEffect, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import './ChatbotWidget.css'

// 오른쪽 하단에 떠 있는 챗봇 버튼 — 누르면 작은 채팅 패널이 열리고, '크게 보기'로 챗봇 페이지로 이동한다
export default function ChatbotWidget() {
  const [open, setOpen] = useState(false)
  const location = useLocation()
  const navigate = useNavigate()

  useEffect(() => {
    if (!open) return
    const onKeyDown = (event) => {
      if (event.key === 'Escape') setOpen(false)
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [open])

  // 챗봇 페이지에서는 이미 크게 보고 있으므로 위젯을 숨긴다
  if (location.pathname === '/chatbot') return null

  function openFullPage() {
    setOpen(false)
    navigate('/chatbot')
  }

  return (
    <div className="chatbot-widget">
      {open && (
        <div className="chatbot-widget__panel" role="dialog" aria-label="여행 챗봇">
          <div className="chatbot-widget__header">
            <span className="chatbot-widget__title">여행 챗봇</span>
            <div className="chatbot-widget__header-actions">
              <button type="button" className="chatbot-widget__link" onClick={openFullPage}>
                크게 보기
              </button>
              <button
                type="button"
                className="chatbot-widget__close"
                aria-label="챗봇 닫기"
                onClick={() => setOpen(false)}
              >
                ✕
              </button>
            </div>
          </div>
          <div className="chatbot-widget__body">
            <p className="chatbot-widget__message">
              RAG 기반 여행 챗봇은 현재 구현 중입니다. 조금만 기다려주세요!
            </p>
          </div>
        </div>
      )}

      <button
        type="button"
        className="chatbot-widget__fab"
        aria-label={open ? '챗봇 닫기' : '챗봇 열기'}
        aria-expanded={open}
        onClick={() => setOpen((prev) => !prev)}
      >
        {open ? '✕' : '💬'}
      </button>
    </div>
  )
}
