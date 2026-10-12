import { useEffect, useState } from 'react'
import {
  CHAT_TTL_MS,
  MAX_PINNED,
  newConversation,
  selectConversation,
  togglePin,
  useRagChat,
} from '../chat/chatStore.js'
import './ChatHistory.css'

function expiryLabel(conversation, now) {
  if (conversation.pinned) return '고정됨'
  const remainingMinutes = Math.max(1, Math.ceil((conversation.createdAt + CHAT_TTL_MS - now) / 60000))
  if (remainingMinutes >= 60) return `${Math.ceil(remainingMinutes / 60)}시간 뒤 사라져요`
  return `${remainingMinutes}분 뒤 사라져요`
}

// 대화 목록 (챗봇 페이지의 왼쪽 목록, 미니 챗봇의 목록 화면에서 같이 쓴다).
// onPick: 대화를 고르거나 새로 시작한 뒤 할 일 (미니 챗봇은 대화 화면으로 돌아간다)
export default function ChatHistory({ onPick, showNewButton = false }) {
  const { conversations, activeId } = useRagChat()
  const [now, setNow] = useState(() => Date.now())
  const [notice, setNotice] = useState('')

  // 남은 시간 표시가 흐르도록 1분마다 다시 그린다
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 60 * 1000)
    return () => clearInterval(id)
  }, [])

  function handlePin(conversation) {
    const result = togglePin(conversation.id)
    setNotice(result === 'limit' ? `고정은 최대 ${MAX_PINNED}개까지 할 수 있어요. 다른 대화의 고정을 풀어 주세요.` : '')
  }

  function handleNew() {
    newConversation()
    onPick?.()
  }

  return (
    <div className="chat-history">
      {showNewButton && (
        <button type="button" className="btn btn-primary chat-history__new" onClick={handleNew}>
          + 새 대화
        </button>
      )}

      {conversations.length === 0 ? (
        <p className="chat-history__empty">아직 저장된 대화가 없어요. 질문을 보내면 여기에 쌓여요.</p>
      ) : (
        <ul className="chat-history__list">
          {conversations.map((conversation) => (
            <li
              key={conversation.id}
              className={`chat-history__item${conversation.id === activeId ? ' chat-history__item--active' : ''}`}
            >
              <button
                type="button"
                className="chat-history__pick"
                aria-current={conversation.id === activeId}
                onClick={() => {
                  selectConversation(conversation.id)
                  onPick?.()
                }}
              >
                <span className="chat-history__title">{conversation.title}</span>
                <span className="chat-history__meta">{expiryLabel(conversation, now)}</span>
              </button>
              <button
                type="button"
                className={`chat-history__pin${conversation.pinned ? ' chat-history__pin--on' : ''}`}
                aria-pressed={conversation.pinned}
                aria-label={conversation.pinned ? '고정 해제' : '대화 고정'}
                title={conversation.pinned ? '고정 해제' : '고정하면 24시간이 지나도 사라지지 않아요'}
                onClick={() => handlePin(conversation)}
              >
                📌
              </button>
            </li>
          ))}
        </ul>
      )}

      {notice && <p className="chat-history__notice chat-history__notice--error">{notice}</p>}
      <p className="chat-history__notice">
        고정하지 않은 대화는 만든 지 24시간 뒤에 사라져요. 중요한 대화는 📌로 고정하세요 (최대 {MAX_PINNED}개).
        고정을 풀면 24시간이 지난 대화는 바로 사라져요. 대화는 이 브라우저에만 저장돼요.
      </p>
    </div>
  )
}
