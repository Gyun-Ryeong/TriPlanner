import { Fragment, useEffect, useRef, useState } from 'react'
import Markdown from 'react-markdown'
import { Link } from 'react-router-dom'
import {
  isDevModeActive,
  resetConversation,
  saveChatPlan,
  sendMessage,
  startChat,
  useRagChat,
} from '../chat/chatStore.js'
import './ChatPanel.css'

// RAG 서버는 모든 답변 끝에 '---' 와 고정 안내문(🛠 개발자 정보)을 붙인다 → 접어서 보여준다
const FOOTER_SEPARATOR = '\n---\n🛠'

const EXAMPLES = ['이번 주말 부산 2박 3일 일정 짜줘', '성남 맛집 알려줘', '제주 축제 알려줘']

function MarkdownLink({ node: _node, ...props }) {
  return <a {...props} target="_blank" rel="noreferrer" />
}

const MARKDOWN_COMPONENTS = { a: MarkdownLink }

function formatTimings(timings) {
  if (!timings) return null
  const parts = [
    timings.collect_sec != null && `데이터 수집 ${timings.collect_sec}초`,
    timings.rank_sec != null && `후보 검색 ${timings.rank_sec}초`,
    timings.llm_sec != null && `AI 일정 ${timings.llm_sec}초`,
  ].filter(Boolean)
  return parts.length ? parts.join(' · ') : JSON.stringify(timings)
}

function DebugInfo({ debug }) {
  const timings = formatTimings(debug.timings)
  return (
    <details className="chat-panel__debug">
      <summary>🧪 디버그 정보 (개발자 모드)</summary>
      {debug.caveats.length > 0 && (
        <ul>
          {debug.caveats.map((caveat, index) => (
            <li key={index}>{caveat}</li>
          ))}
        </ul>
      )}
      {timings && <p>소요 시간: {timings}</p>}
      {debug.timings?.tasks && Object.keys(debug.timings.tasks).length > 0 && (
        <p>항목별: {JSON.stringify(debug.timings.tasks)}</p>
      )}
      {debug.llmStats && <p>AI: {JSON.stringify(debug.llmStats)}</p>}
    </details>
  )
}

// 챗봇이 만든 일정을 '내 여행'에 저장하는 버튼. 저장 후에는 일정 화면에서 직접 고칠 수 있다
function PlanSaveBar({ messageIndex, plans, saved }) {
  const [busyIndex, setBusyIndex] = useState(null)
  const [error, setError] = useState('')

  async function handleSave(planIndex) {
    if (busyIndex !== null) return
    setBusyIndex(planIndex)
    setError('')
    try {
      await saveChatPlan(messageIndex, planIndex)
    } catch (err) {
      setError(err.message ?? '일정을 저장하지 못했습니다.')
    } finally {
      setBusyIndex(null)
    }
  }

  return (
    <div className="chat-panel__save">
      {plans.map((plan, planIndex) =>
        saved?.[planIndex] ? (
          <Link key={planIndex} to={`/schedule/${saved[planIndex]}`} className="chat-panel__saved-link">
            ✅ {plan.request.title} 저장됨 · 보기/수정하기 →
          </Link>
        ) : (
          <button
            key={planIndex}
            type="button"
            className="btn btn-primary chat-panel__save-button"
            disabled={busyIndex !== null}
            onClick={() => handleSave(planIndex)}
          >
            {busyIndex === planIndex ? '저장 중...' : `💾 ${plans.length > 1 ? `${plan.label} ` : ''}일정 내 여행에 저장`}
          </button>
        ),
      )}
      {error && <p className="chat-panel__save-error">{error}</p>}
    </div>
  )
}

function AssistantMessage({ content, debug }) {
  const footerIndex = content.indexOf(FOOTER_SEPARATOR)
  const body = footerIndex === -1 ? content : content.slice(0, footerIndex)
  const footer = footerIndex === -1 ? '' : content.slice(footerIndex + '\n---\n'.length)
  const [footerTitle, ...footerLines] = footer.split('\n')

  return (
    <div className="chat-panel__bubble chat-panel__bubble--assistant">
      <div className="chat-panel__markdown">
        <Markdown components={MARKDOWN_COMPONENTS}>{body}</Markdown>
      </div>
      {footer && (
        <details className="chat-panel__footer">
          <summary>{footerTitle}</summary>
          <div className="chat-panel__markdown">
            <Markdown components={MARKDOWN_COMPONENTS}>{footerLines.join('\n')}</Markdown>
          </div>
        </details>
      )}
      {debug && <DebugInfo debug={debug} />}
    </div>
  )
}

export default function ChatPanel({ compact = false }) {
  const chatState = useRagChat()
  const { messages, pending } = chatState
  const devMode = isDevModeActive(chatState)
  const [input, setInput] = useState('')
  const listRef = useRef(null)

  useEffect(() => {
    startChat()
  }, [])

  useEffect(() => {
    const list = listRef.current
    if (list) list.scrollTop = list.scrollHeight
  }, [messages, pending])

  function submit(text) {
    if (!text.trim() || pending) return
    sendMessage(text)
    setInput('')
  }

  function handleKeyDown(event) {
    // 한글 입력 중(조합 중) Enter 는 글자 확정용이라 전송하지 않는다
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault()
      submit(input)
    }
  }

  const showExamples = !pending && messages.length === 1 && messages[0].role === 'assistant'

  return (
    <div className={`chat-panel${compact ? ' chat-panel--compact' : ''}`}>
      <div className="chat-panel__toolbar">
        {devMode && <span className="chat-panel__dev-badge">🛠 개발자 모드</span>}
        <button type="button" className="chat-panel__reset" onClick={resetConversation} disabled={pending}>
          새 대화
        </button>
      </div>

      <div className="chat-panel__messages" ref={listRef} aria-live="polite">
        {messages.map((message, index) =>
          message.role === 'assistant' ? (
            <Fragment key={index}>
              <AssistantMessage content={message.content} debug={devMode ? message.debug : null} />
              {message.plans?.length > 0 && (
                <PlanSaveBar messageIndex={index} plans={message.plans} saved={message.saved} />
              )}
            </Fragment>
          ) : (
            <div key={index} className={`chat-panel__bubble chat-panel__bubble--${message.role}`}>
              {message.content}
            </div>
          ),
        )}

        {pending && (
          <div className="chat-panel__bubble chat-panel__bubble--assistant chat-panel__pending">
            답변을 준비하고 있어요… 일정을 만들 때는 1~3분 정도 걸릴 수 있어요.
          </div>
        )}

        {showExamples && (
          <div className="chat-panel__examples">
            {EXAMPLES.map((example) => (
              <button key={example} type="button" className="chat-panel__example" onClick={() => submit(example)}>
                {example}
              </button>
            ))}
          </div>
        )}
      </div>

      <form
        className="chat-panel__form"
        onSubmit={(event) => {
          event.preventDefault()
          submit(input)
        }}
      >
        <textarea
          className="chat-panel__input"
          rows={compact ? 3 : 2}
          maxLength={1000}
          placeholder="예: 다음 주 강릉 1박 2일, 바다 보면서 쉬고 싶어요"
          value={input}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={handleKeyDown}
        />
        <button type="submit" className="btn btn-primary chat-panel__send" disabled={pending || !input.trim()}>
          전송
        </button>
      </form>
    </div>
  )
}
