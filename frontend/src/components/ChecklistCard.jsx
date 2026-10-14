import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getChecklist, setChecklistItemChecked } from '../api/trips.js'
import { dueBadge, formatDueDate, relevantItems } from '../lib/checklist.js'
import { ClipboardIcon } from './Icons.jsx'
import './ChecklistCard.css'

const VISIBLE_ITEMS = 4

// 홈 화면의 체크리스트 카드: 다가오는 여행의 준비 진행률과 지금 챙길 항목을 보여준다. loading: 여행을 아직 불러오는 중
export default function ChecklistCard({ trip, loading = false }) {
  const [items, setItems] = useState(null)
  const [error, setError] = useState('')
  const [busyId, setBusyId] = useState(null)

  useEffect(() => {
    if (!trip) return
    let cancelled = false
    setItems(null)
    setError('')

    getChecklist(trip.tripId)
      .then((data) => {
        if (!cancelled) setItems(data)
      })
      .catch((err) => {
        if (!cancelled) setError(err.message ?? '체크리스트를 불러오지 못했습니다.')
      })

    return () => {
      cancelled = true
    }
  }, [trip?.tripId])

  async function toggle(item) {
    setBusyId(item.itemId)
    setError('')
    try {
      const updated = await setChecklistItemChecked(trip.tripId, item.itemId, !item.checked)
      setItems((prev) => prev.map((p) => (p.itemId === updated.itemId ? updated : p)))
    } catch (err) {
      setError(err.message ?? '저장하지 못했습니다.')
    } finally {
      setBusyId(null)
    }
  }

  if (loading) {
    return (
      <div className="card checklist-card">
        <div className="card-head">
          <h2 className="card-title">출발 전 체크리스트</h2>
        </div>
        <p className="checklist-card__empty">불러오는 중...</p>
      </div>
    )
  }

  if (!trip) {
    return (
      <div className="card checklist-card">
        <div className="card-head">
          <h2 className="card-title">출발 전 체크리스트</h2>
        </div>
        <div className="empty-state checklist-card__blank">
          <span className="empty-state__icon"><ClipboardIcon size={22} /></span>
          <p className="empty-state__title">체크할 항목이 없어요</p>
          <p className="empty-state__desc">여행을 만들면 준비할 일이<br />여기에 정리돼요.</p>
        </div>
      </div>
    )
  }

  const shown = items ? relevantItems(items) : []
  const total = shown.length
  const done = shown.filter((item) => item.checked).length
  const percent = total === 0 ? 0 : Math.round((done / total) * 100)
  const remaining = shown.filter((item) => !item.checked)
  const nextItems = remaining.slice(0, VISIBLE_ITEMS)

  return (
    <div className="card checklist-card">
      <div className="card-head checklist-card__head">
        <h2 className="card-title">출발 전 체크리스트</h2>
        <Link to={`/trips/${trip.tripId}/checklist`} className="card-link">
          전체 보기{items !== null && remaining.length > VISIBLE_ITEMS ? ` (${remaining.length - VISIBLE_ITEMS}개 더)` : ''}
        </Link>
      </div>
      <p className="checklist-card__trip">{trip.title}</p>
      {items === null && !error && <p className="checklist-card__empty">불러오는 중...</p>}
      {error && <p className="checklist-card__error">{error}</p>}

      {items !== null && (
        <>
          <p className="checklist-card__main">
            {done}/{total} <span className="checklist-card__unit">완료</span>
          </p>
          <div
            className="checklist-card__bar"
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={percent}
            aria-label="준비 진행률"
          >
            <div className="checklist-card__bar-fill" style={{ width: `${percent}%` }} />
          </div>
          {total === 0 ? (
            <p className="checklist-card__empty">
              {items.length > 0 ? '지금 준비할 항목이 없어요.' : '항목이 없어요. 전체 보기에서 직접 추가할 수 있어요.'}
            </p>
          ) : remaining.length === 0 ? (
            <p className="checklist-card__done">준비를 모두 마쳤어요. 즐거운 여행 되세요!</p>
          ) : (
            <ul className="checklist-card__list">
              {nextItems.map((item) => (
                <li key={item.itemId}>
                  <label className="checklist-card__item">
                    <input
                      type="checkbox"
                      checked={item.checked}
                      disabled={busyId === item.itemId}
                      onChange={() => toggle(item)}
                    />
                    <span className="checklist-card__text">{item.content}</span>
                    <span className="checklist-card__due" title={`${formatDueDate(item.dueDate)}까지`}>
                      {dueBadge(item.dueOffsetDays)}
                    </span>
                  </label>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  )
}
