import ChatPanel from '../components/ChatPanel.jsx'
import './Chatbot.css'

export default function Chatbot() {
  return (
    <div className="chatbot">
      <div className="card chatbot__card">
        <div className="chatbot__header">
          <h1 className="chatbot__title">AI 여행 챗봇</h1>
          <p className="chatbot__subtitle">
            날씨·미세먼지·최신 소식을 반영해 여행 일정과 맛집·숙소·축제를 추천해 드려요.
          </p>
        </div>
        <ChatPanel />
      </div>
    </div>
  )
}
