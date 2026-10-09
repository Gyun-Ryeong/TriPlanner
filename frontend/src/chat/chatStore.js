import { useSyncExternalStore } from 'react'
import { AUTH_CHANGED_EVENT, getAuth } from '../api/authStorage.js'
import { resetChat, sendChatMessage } from '../api/chat.js'
import { importChatPlan } from '../api/trips.js'
import { toSavablePlans } from './planExport.js'

// 챗봇 페이지와 플로팅 위젯이 같은 대화를 이어가도록 대화 상태를 한 곳에서 관리한다.
// 위젯에서 질문하고 '크게 보기'로 넘어가도 답변이 이어서 표시된다.
const STORAGE_KEY = 'triplanner_chat'
const DEV_MODE_KEY = 'triplanner_chat_dev_mode'
const EMPTY = { userId: null, sessionId: null, messages: [], pending: false, devMode: false }

const listeners = new Set()
let state = { ...load(), devMode: loadDevMode() }
// 대화를 초기화하면 늘어나서, 그 전에 보낸 요청의 응답은 버린다
let generation = 0

function currentUserId() {
  return getAuth()?.userId ?? null
}

function isAdmin() {
  return getAuth()?.admin === true
}

// 챗봇 개발자 모드: 관리자 페이지에서 켜고 끄며, 이 브라우저에만 저장된다
function loadDevMode() {
  try {
    return localStorage.getItem(DEV_MODE_KEY) === 'on'
  } catch {
    return false
  }
}

function load() {
  try {
    const saved = JSON.parse(sessionStorage.getItem(STORAGE_KEY))
    // 다른 계정의 대화는 보여주지 않는다
    if (saved && saved.userId === currentUserId()) return { ...EMPTY, ...saved }
  } catch {
    // 저장된 값이 없거나 깨졌으면 새 대화로 시작
  }
  return { ...EMPTY, userId: currentUserId() }
}

function setState(next) {
  state = next
  try {
    const { userId, sessionId, messages } = state
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ userId, sessionId, messages }))
  } catch {
    // 저장소를 못 써도 화면의 대화는 유지된다
  }
  listeners.forEach((listener) => listener())
}

function subscribe(listener) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

window.addEventListener(AUTH_CHANGED_EVENT, () => {
  if (state.userId !== currentUserId()) {
    generation += 1
    setState({ ...EMPTY, userId: currentUserId(), devMode: state.devMode })
  }
})

// 개발자 모드 응답에만 들어 있는 내부 정보 (API 오류·소요 시간·AI 속도)
function debugInfo(data) {
  const caveats = data.caveats ?? []
  if (caveats.length === 0 && !data.timings && !data.llm_stats) return null
  return { caveats, timings: data.timings ?? null, llmStats: data.llm_stats ?? null }
}

async function request(message) {
  const requestGeneration = generation
  setState({ ...state, pending: true })
  try {
    const data = await sendChatMessage(state.sessionId, message, isAdmin() && state.devMode)
    if (requestGeneration !== generation) return
    setState({
      ...state,
      // RAG 서버가 재시작돼 세션이 사라졌으면 새 session_id 가 오므로 항상 갱신한다
      sessionId: data.session_id,
      pending: false,
      messages: [
        ...state.messages,
        // plans: '내 여행에 저장'할 수 있는 일정, saved: 저장된 일정의 tripId (plans 순서 기준)
        { role: 'assistant', content: data.reply, debug: debugInfo(data), plans: toSavablePlans(data), saved: {} },
      ],
    })
  } catch (error) {
    if (requestGeneration !== generation) return
    setState({ ...state, pending: false, messages: [...state.messages, { role: 'error', content: error.message }] })
  }
}

// 처음 열었을 때 인사말을 받아온다
export function startChat() {
  if (state.messages.length === 0 && !state.pending) request('')
}

export function sendMessage(text) {
  const message = text.trim()
  if (!message || state.pending) return
  setState({ ...state, messages: [...state.messages, { role: 'user', content: message }] })
  request(message)
}

export function resetConversation() {
  if (state.sessionId) resetChat(state.sessionId).catch(() => {})
  generation += 1
  setState({ ...EMPTY, userId: state.userId, devMode: state.devMode })
  request('')
}

// 답변에 담긴 일정을 '내 여행'으로 저장하고 저장된 여행 정보를 돌려준다
export async function saveChatPlan(messageIndex, planIndex) {
  const message = state.messages[messageIndex]
  const plan = message?.plans?.[planIndex]
  if (!plan) throw new Error('저장할 일정을 찾지 못했습니다.')

  const trip = await importChatPlan(plan.request)
  // 저장하는 사이 대화를 초기화했으면 표시만 건너뛴다 (여행은 이미 저장됨)
  if (state.messages[messageIndex] === message) {
    const updated = { ...message, saved: { ...message.saved, [planIndex]: trip.tripId } }
    setState({ ...state, messages: state.messages.map((m, i) => (i === messageIndex ? updated : m)) })
  }
  return trip
}

export function setDevMode(enabled) {
  try {
    localStorage.setItem(DEV_MODE_KEY, enabled ? 'on' : 'off')
  } catch {
    // 저장소를 못 써도 이번 화면에서는 적용된다
  }
  setState({ ...state, devMode: enabled })
}

// 관리자 계정에서 개발자 모드를 켰을 때만 디버그 정보를 보여준다
export function isDevModeActive(chatState) {
  return chatState.devMode && isAdmin()
}

export function useRagChat() {
  return useSyncExternalStore(subscribe, () => state)
}
