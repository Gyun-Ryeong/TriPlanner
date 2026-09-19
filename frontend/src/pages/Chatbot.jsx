import { useState } from 'react'
import './Chatbot.css'

const RECENT_CHATS = ['경주 2박 3일 일정', '가을 경주 여행 준비물', '경북 교통편 추천']

const INITIAL_MESSAGES = [
  {
    from: 'bot',
    text: '안녕하세요, 민지님! 최신 여행 정보를 바탕으로 무엇이든 도와드릴게요. 어디로 떠나시나요?',
  },
  {
    from: 'user',
    text: '10월 경주 2박 3일 일정을 추천해줘. 맛집과 불국사도 넣어줘!',
  },
  {
    from: 'bot',
    text: '좋아요! 이동 동선을 고려한 맞춤 일정을 만들었어요.',
    itinerary: [
      '1일차: 불국사 · 석굴암 · 보문단지',
      '2일차: 경주 동궁과 월지 · 첨성대 · 황리단길',
      '3일차: 양동마을 · 교촌마을',
    ],
  },
]

export default function Chatbot() {
  const [input, setInput] = useState('')

  return (
    <div className="chatbot">
      <aside className="chatbot__sidebar">
        <h3 className="chatbot__sidebar-title">최근 대화</h3>
        <ul className="chatbot__history">
          {RECENT_CHATS.map((title, i) => (
            <li key={title} className={i === 0 ? 'chatbot__history-item chatbot__history-item--active' : 'chatbot__history-item'}>
              {title}
            </li>
          ))}
        </ul>
      </aside>

      <section className="chatbot__panel card">
        <h2 className="chatbot__title">RAG 기반 여행 챗봇</h2>

        <div className="chatbot__messages">
          {INITIAL_MESSAGES.map((msg, i) => (
            <div key={i} className={msg.from === 'user' ? 'chatbot__bubble chatbot__bubble--user' : 'chatbot__bubble chatbot__bubble--bot'}>
              <p>{msg.text}</p>
              {msg.itinerary && (
                <ul>
                  {msg.itinerary.map((line) => (
                    <li key={line}>{line}</li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </div>

        <form className="chatbot__input" onSubmit={(e) => e.preventDefault()}>
          <input
            type="text"
            placeholder="여행에 대해 무엇이든 물어보세요"
            value={input}
            onChange={(e) => setInput(e.target.value)}
          />
          <button type="submit" aria-label="전송">→</button>
        </form>
      </section>
    </div>
  )
}
