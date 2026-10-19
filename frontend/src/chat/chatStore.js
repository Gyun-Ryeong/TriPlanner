import { useSyncExternalStore } from 'react'
import { AUTH_CHANGED_EVENT, getAuth } from '../api/authStorage.js'
import { resetChat, sendChatMessage } from '../api/chat.js'
import { importChatPlan } from '../api/trips.js'
import { toSavablePlans } from './planExport.js'

// 챗봇 페이지와 플로팅 위젯이 같은 대화 목록을 보도록 대화 상태를 한 곳에서 관리한다.
// 대화는 이 브라우저(localStorage)에 계정별로 저장하고, 고정(핀)하지 않은 대화는 만든 지 24시간 뒤에 지운다.
const STORAGE_PREFIX = 'triplanner_chats_'
const DEV_MODE_KEY = 'triplanner_chat_dev_mode'

export const CHAT_TTL_MS = 24 * 60 * 60 * 1000
export const MAX_CHATS = 10
export const MAX_PINNED = 5
const NEW_CHAT_TITLE = '새 대화'
export const TITLE_MAX_LENGTH = 20

const listeners = new Set()
// 응답을 기다리는 대화 id. 다른 대화로 옮겨도 응답은 원래 대화에 붙는다
const pendingIds = new Set()
let devMode = loadDevMode()
let data = load(currentUserId())
// 저장해 둔 대화 중 이미 24시간이 지난 것은 처음부터 지운다
purgeExpired()
let state = buildState()

function currentUserId() {
  return getAuth()?.userId ?? null
}

function isAdmin() {
  return getAuth()?.admin === true
}

function storageKey(userId) {
  return `${STORAGE_PREFIX}${userId ?? 'anonymous'}`
}

// 챗봇 개발자 모드: 관리자 페이지에서 켜고 끄며, 이 브라우저에만 저장된다
function loadDevMode() {
  try {
    return localStorage.getItem(DEV_MODE_KEY) === 'on'
  } catch {
    return false
  }
}

function emptyData(userId) {
  return { userId, activeId: null, conversations: [] }
}

function load(userId) {
  try {
    const saved = JSON.parse(localStorage.getItem(storageKey(userId)))
    if (saved && Array.isArray(saved.conversations)) {
      return { userId, activeId: saved.activeId ?? null, conversations: saved.conversations }
    }
  } catch {
    // 저장된 값이 없거나 깨졌으면 새로 시작
  }
  return emptyData(userId)
}

function persist() {
  try {
    const { activeId, conversations } = data
    localStorage.setItem(storageKey(data.userId), JSON.stringify({ activeId, conversations }))
  } catch {
    // 저장소를 못 써도 화면의 대화는 유지된다
  }
}

function newId() {
  return `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 8)}`
}

function hasUserMessage(conversation) {
  return conversation.messages.some((message) => message.role === 'user')
}

function findConversation(id) {
  return data.conversations.find((conversation) => conversation.id === id) ?? null
}

function isExpired(conversation, now) {
  return !conversation.pinned && now - conversation.createdAt >= CHAT_TTL_MS
}

// 서버(RAG)에 남은 대화 기억도 함께 정리한다
function discard(conversations) {
  conversations.forEach((conversation) => {
    pendingIds.delete(conversation.id)
    if (conversation.sessionId) resetChat(conversation.sessionId).catch(() => {})
  })
}

// 고정하지 않은 채 24시간이 지난 대화를 지운다. 지운 게 있으면 true
function purgeExpired() {
  const now = Date.now()
  const expired = data.conversations.filter((conversation) => isExpired(conversation, now))
  if (expired.length === 0) return false
  data = { ...data, conversations: data.conversations.filter((conversation) => !expired.includes(conversation)) }
  if (!findConversation(data.activeId)) data = { ...data, activeId: null }
  discard(expired)
  return true
}

function buildState() {
  const active = findConversation(data.activeId)
  // 목록에는 사용자가 한 번이라도 말을 건 대화만 보여준다 (인사말만 있는 새 대화는 제외). 고정 먼저, 그 안에서는 최신순
  const conversations = data.conversations
    .filter(hasUserMessage)
    .sort((a, b) => Number(b.pinned) - Number(a.pinned) || b.createdAt - a.createdAt)
  return {
    userId: data.userId,
    devMode,
    activeId: data.activeId,
    conversations,
    pinnedCount: conversations.filter((conversation) => conversation.pinned).length,
    sessionId: active?.sessionId ?? null,
    messages: active?.messages ?? [],
    pending: active ? pendingIds.has(active.id) : false,
  }
}

function commit() {
  purgeExpired()
  state = buildState()
  persist()
  listeners.forEach((listener) => listener())
}

function patchConversation(id, update) {
  data = {
    ...data,
    conversations: data.conversations.map((conversation) => (conversation.id === id ? update(conversation) : conversation)),
  }
}

function subscribe(listener) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

window.addEventListener(AUTH_CHANGED_EVENT, () => {
  if (data.userId !== currentUserId()) {
    pendingIds.clear()
    data = load(currentUserId())
    commit()
  }
})

// 다른 탭에서 대화를 바꾸면 이 탭도 같은 내용을 보여준다
window.addEventListener('storage', (event) => {
  if (event.key !== storageKey(data.userId)) return
  const active = data.activeId
  data = load(data.userId)
  if (!findConversation(data.activeId) && findConversation(active)) data = { ...data, activeId: active }
  state = buildState()
  listeners.forEach((listener) => listener())
})

// 탭을 열어 둔 채 24시간이 지나는 대화도 지운다
setInterval(() => {
  if (purgeExpired()) commit()
}, 60 * 1000)

// 개발자 모드 응답에만 들어 있는 내부 정보 (API 오류·소요 시간·AI 속도·일정 품질 지표)
function debugInfo(response) {
  const caveats = response.caveats ?? []
  if (caveats.length === 0 && !response.timings && !response.llm_stats && !response.evaluation) return null
  return {
    caveats,
    timings: response.timings ?? null,
    llmStats: response.llm_stats ?? null,
    evaluation: response.evaluation ?? null,
  }
}

async function request(id, message) {
  const conversation = findConversation(id)
  if (!conversation) return
  pendingIds.add(id)
  commit()
  try {
    const response = await sendChatMessage(conversation.sessionId, message, isAdmin() && devMode)
    // 응답을 기다리는 사이 지워진 대화면 버린다
    if (!findConversation(id)) return
    patchConversation(id, (c) => ({
      ...c,
      // RAG 서버가 재시작돼 세션이 사라졌으면 새 session_id 가 오므로 항상 갱신한다
      sessionId: response.session_id,
      messages: [
        ...c.messages,
        // plans: '내 여행에 저장'할 수 있는 일정, saved: 저장된 일정의 tripId (plans 순서 기준)
        { role: 'assistant', content: response.reply, debug: debugInfo(response), plans: toSavablePlans(response), saved: {} },
      ],
    }))
  } catch (error) {
    if (findConversation(id)) {
      patchConversation(id, (c) => ({ ...c, messages: [...c.messages, { role: 'error', content: error.message }] }))
    }
  } finally {
    pendingIds.delete(id)
    commit()
  }
}

// 사용자가 말을 걸지 않은(인사말뿐인) 대화는 목록에 남기지 않고 정리한다
function dropIfUnused(id) {
  const conversation = findConversation(id)
  if (!conversation || hasUserMessage(conversation)) return
  data = { ...data, conversations: data.conversations.filter((c) => c.id !== id) }
  discard([conversation])
}

function createConversation() {
  dropIfUnused(data.activeId)

  // 10개를 넘기지 않도록 고정하지 않은 가장 오래된 대화부터 지운다 (고정은 최대 5개라 지울 대화가 항상 있다)
  while (data.conversations.length >= MAX_CHATS) {
    const oldest = data.conversations.filter((c) => !c.pinned).sort((a, b) => a.createdAt - b.createdAt)[0]
    if (!oldest) break
    data = { ...data, conversations: data.conversations.filter((c) => c !== oldest) }
    discard([oldest])
  }

  const conversation = { id: newId(), sessionId: null, title: NEW_CHAT_TITLE, createdAt: Date.now(), pinned: false, messages: [] }
  data = { ...data, activeId: conversation.id, conversations: [...data.conversations, conversation] }
  request(conversation.id, '')
}

// 처음 열었을 때 열려 있는 대화가 없으면 새로 만들고, 인사말이 없으면 받아온다
export function startChat() {
  purgeExpired()
  const active = findConversation(data.activeId)
  if (!active) createConversation()
  else if (active.messages.length === 0 && !pendingIds.has(active.id)) request(active.id, '')
}

export function sendMessage(text) {
  const message = text.trim()
  const active = findConversation(data.activeId)
  if (!message || !active || pendingIds.has(active.id)) return
  patchConversation(active.id, (c) => ({
    ...c,
    // 대화 제목은 첫 질문의 앞부분
    title: hasUserMessage(c) ? c.title : message.length > TITLE_MAX_LENGTH ? `${message.slice(0, TITLE_MAX_LENGTH)}…` : message,
    messages: [...c.messages, { role: 'user', content: message }],
  }))
  commit()
  request(active.id, message)
}

// 지금 대화를 목록에 남겨 두고 새 대화를 시작한다. 이미 새 대화(말을 걸기 전)면 그대로 둔다
export function newConversation() {
  const active = findConversation(data.activeId)
  if (active && !hasUserMessage(active)) return
  createConversation()
}

export function selectConversation(id) {
  if (!findConversation(id) || id === data.activeId) return
  dropIfUnused(data.activeId)
  data = { ...data, activeId: id }
  commit()
}

// 대화 제목을 바꾼다 (앞뒤 공백 제거, 최대 TITLE_MAX_LENGTH 자). 'renamed' | 'unchanged' | 'empty'(빈 제목은 저장 안 함) | 'missing'
export function renameConversation(id, title) {
  const conversation = findConversation(id)
  if (!conversation) return 'missing'
  const next = title.trim().slice(0, TITLE_MAX_LENGTH)
  if (!next) return 'empty'
  if (next === conversation.title) return 'unchanged'
  patchConversation(id, (c) => ({ ...c, title: next }))
  commit()
  return 'renamed'
}

// 'pinned' | 'unpinned' | 'limit'(고정 개수 초과) | 'missing'. 고정을 풀었을 때 24시간이 지난 대화는 바로 지워진다
export function togglePin(id) {
  const conversation = findConversation(id)
  if (!conversation) return 'missing'
  if (!conversation.pinned && state.pinnedCount >= MAX_PINNED) return 'limit'
  patchConversation(id, (c) => ({ ...c, pinned: !c.pinned }))
  commit()
  return conversation.pinned ? 'unpinned' : 'pinned'
}

// 대화 하나를 바로 지운다 (서버의 대화 기억도 함께). 고정된 대화는 지우지 않고 'pinned' 를 돌려준다.
// 열려 있던 대화를 지우면 열린 대화가 없는 상태가 되고, 챗봇 화면이 열려 있으면 새 대화를 시작한다
// 'deleted' | 'pinned' | 'missing'
export function deleteConversation(id) {
  const conversation = findConversation(id)
  if (!conversation) return 'missing'
  if (conversation.pinned) return 'pinned'
  data = { ...data, conversations: data.conversations.filter((c) => c.id !== id) }
  if (data.activeId === id) data = { ...data, activeId: null }
  discard([conversation])
  commit()
  return 'deleted'
}

// 답변에 담긴 일정을 '내 여행'으로 저장하고 저장된 여행 정보를 돌려준다
export async function saveChatPlan(messageIndex, planIndex) {
  const conversationId = data.activeId
  const message = findConversation(conversationId)?.messages[messageIndex]
  const plan = message?.plans?.[planIndex]
  if (!plan) throw new Error('저장할 일정을 찾지 못했습니다.')

  const trip = await importChatPlan(plan.request)
  // 저장하는 사이 대화가 지워졌으면 표시만 건너뛴다 (여행은 이미 저장됨)
  if (findConversation(conversationId)?.messages[messageIndex] === message) {
    const updated = { ...message, saved: { ...message.saved, [planIndex]: trip.tripId } }
    patchConversation(conversationId, (c) => ({ ...c, messages: c.messages.map((m, i) => (i === messageIndex ? updated : m)) }))
    commit()
  }
  return trip
}

export function setDevMode(enabled) {
  try {
    localStorage.setItem(DEV_MODE_KEY, enabled ? 'on' : 'off')
  } catch {
    // 저장소를 못 써도 이번 화면에서는 적용된다
  }
  devMode = enabled
  commit()
}

// 관리자 계정에서 개발자 모드를 켰을 때만 디버그 정보를 보여준다
export function isDevModeActive(chatState) {
  return chatState.devMode && isAdmin()
}

export function useRagChat() {
  return useSyncExternalStore(subscribe, () => state)
}
