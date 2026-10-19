import { useState } from 'react'
import ChatHistory from '../components/ChatHistory.jsx'
import ChatPanel from '../components/ChatPanel.jsx'
import './Chatbot.css'

export default function Chatbot() {
  // 좁은 화면에서는 대화 목록을 접어 두고 버튼으로 연다
  const [listOpen, setListOpen] = useState(false)

  return (
    <div className="chatbot">
      <div className="card chatbot__card">
        <div className="chatbot__header">
          <div>
            <h1 className="chatbot__title">AI 여행 챗봇</h1>
            <p className="chatbot__subtitle">
              날씨·미세먼지·최신 소식을 반영해 여행 일정과 맛집·숙소·축제를 추천해 드려요.
            </p>
          </div>
          <button
            type="button"
            className="btn chatbot__list-toggle"
            aria-expanded={listOpen}
            onClick={() => setListOpen((prev) => !prev)}
          >
            대화 목록
          </button>
        </div>
        <div className="chatbot__body">
          <aside className={`chatbot__side${listOpen ? ' chatbot__side--open' : ''}`} aria-label="대화 목록">
            <ChatHistory onPick={() => setListOpen(false)} />
          </aside>
          <div className="chatbot__main">
            <ChatPanel />
          </div>
        </div>
      </div>
    </div>
  )
}
