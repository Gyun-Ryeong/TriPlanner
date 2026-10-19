import { useCallback, useEffect, useRef, useState } from 'react'
import { PencilIcon } from './Icons.jsx'
import Toast from './Toast.jsx'
import {
  CHAT_TTL_MS,
  MAX_PINNED,
  TITLE_MAX_LENGTH,
  deleteConversation,
  newConversation,
  renameConversation,
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
  const [toast, setToast] = useState(null)
  const clearToast = useCallback(() => setToast(null), [])
  const [editingId, setEditingId] = useState(null)
  const [draft, setDraft] = useState('')
  const renameDoneRef = useRef(true)

  // 남은 시간 표시가 흐르도록 1분마다 다시 그린다
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 60 * 1000)
    return () => clearInterval(id)
  }, [])

  function startRename(conversation) {
    renameDoneRef.current = false
    setDraft(conversation.title)
    setEditingId(conversation.id)
  }

  // 저장(Enter·입력칸 밖 클릭)과 취소(Esc)를 한 번만 처리한다. 저장하면서 입력칸이 사라질 때 blur 가 또 오는 것을 막는다
  function finishRename(save) {
    if (renameDoneRef.current) return
    renameDoneRef.current = true
    const id = editingId
    setEditingId(null)
    if (save && id) renameConversation(id, draft)
  }

  function handleRenameKeyDown(event) {
    // 한글 조합 중에 누른 Enter 는 글자 확정이므로 저장으로 보지 않는다
    if (event.nativeEvent.isComposing) return
    if (event.key === 'Enter') finishRename(true)
    else if (event.key === 'Escape') finishRename(false)
  }

  function handlePin(conversation) {
    const result = togglePin(conversation.id)
    setNotice(result === 'limit' ? `고정은 최대 ${MAX_PINNED}개까지 할 수 있어요. 다른 대화의 고정을 풀어 주세요.` : '')
  }

  // 고정하지 않은 대화는 확인 후 바로 지우고, 고정된 대화는 지우지 않고 먼저 고정을 풀라고 안내한다
  function handleDelete(conversation) {
    if (conversation.pinned) {
      setToast({ id: Date.now(), text: '고정된 대화예요. 📌 고정을 먼저 해제한 뒤 삭제해 주세요.', kind: 'warn' })
      return
    }
    if (!window.confirm('이 대화를 정말 삭제할까요? 삭제한 대화는 되돌릴 수 없어요.')) return
    deleteConversation(conversation.id)
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
              {editingId === conversation.id ? (
                <input
                  className="chat-history__rename-input"
                  value={draft}
                  maxLength={TITLE_MAX_LENGTH}
                  aria-label="대화 제목 수정"
                  autoFocus
                  onFocus={(event) => event.target.select()}
                  onChange={(event) => setDraft(event.target.value)}
                  onKeyDown={handleRenameKeyDown}
                  onBlur={() => finishRename(true)}
                />
              ) : (
                <>
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
                    className="chat-history__rename"
                    aria-label={`${conversation.title} 제목 수정`}
                    title="제목 수정"
                    onClick={() => startRename(conversation)}
                  >
                    <PencilIcon size={14} />
                  </button>
                </>
              )}
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
              <button
                type="button"
                className="chat-history__delete"
                aria-label={`${conversation.title} 대화 삭제`}
                title="이 대화 삭제"
                onClick={() => handleDelete(conversation)}
              >
                ✕
              </button>
            </li>
          ))}
        </ul>
      )}

      {notice && <p className="chat-history__notice chat-history__notice--error">{notice}</p>}
      <p className="chat-history__notice">
        고정하지 않은 대화는 만든 지 24시간 뒤에 사라져요. 중요한 대화는 📌로 고정하세요 (최대 {MAX_PINNED}개).
        고정을 풀면 24시간이 지난 대화는 바로 사라져요. 필요 없는 대화는 ✕로 바로 지울 수 있어요. 대화는 이 브라우저에만 저장돼요.
      </p>
      <Toast message={toast} onClose={clearToast} duration={3000} />
    </div>
  )
}
