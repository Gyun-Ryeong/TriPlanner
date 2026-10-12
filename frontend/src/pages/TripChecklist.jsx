import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  addChecklistItem,
  deleteChecklistItem,
  getChecklist,
  getTrip,
  setChecklistItemChecked,
} from '../api/trips.js'
import { CATEGORY_LABELS, DUE_OPTIONS, dueBadge, formatDueDate, isOverdue } from '../lib/checklist.js'
import './TripChecklist.css'

const CONTENT_MAX_LENGTH = 100

export default function TripChecklist() {
  const { tripId } = useParams()
  const [trip, setTrip] = useState(null)
  const [items, setItems] = useState(null)
  const [loadError, setLoadError] = useState('')
  const [actionError, setActionError] = useState('')
  const [busyId, setBusyId] = useState(null)
  const [content, setContent] = useState('')
  const [dueOffsetDays, setDueOffsetDays] = useState(1)

  useEffect(() => {
    let cancelled = false
    setTrip(null)
    setItems(null)
    setLoadError('')

    Promise.all([getTrip(tripId), getChecklist(tripId)])
      .then(([tripData, checklist]) => {
        if (cancelled) return
        setTrip(tripData)
        setItems(checklist)
      })
      .catch((err) => {
        if (!cancelled) setLoadError(err.message ?? '체크리스트를 불러오지 못했습니다.')
      })

    return () => {
      cancelled = true
    }
  }, [tripId])

  async function run(id, action) {
    setBusyId(id)
    setActionError('')
    try {
      await action()
    } catch (err) {
      setActionError(err.message ?? '처리하지 못했습니다.')
    } finally {
      setBusyId(null)
    }
  }

  function handleToggle(item) {
    return run(item.itemId, async () => {
      const updated = await setChecklistItemChecked(tripId, item.itemId, !item.checked)
      setItems((prev) => prev.map((p) => (p.itemId === updated.itemId ? updated : p)))
    })
  }

  function handleDelete(item) {
    return run(item.itemId, async () => {
      await deleteChecklistItem(tripId, item.itemId)
      setItems((prev) => prev.filter((p) => p.itemId !== item.itemId))
    })
  }

  function handleAdd(event) {
    event.preventDefault()
    const text = content.trim()
    if (!text) return
    return run('add', async () => {
      const created = await addChecklistItem(tripId, { content: text, dueOffsetDays })
      setItems((prev) =>
        [...prev, created].sort((a, b) => b.dueOffsetDays - a.dueOffsetDays || a.itemId - b.itemId)
      )
      setContent('')
    })
  }

  if (loadError) {
    return (
      <div className="trip-checklist">
        <p className="trip-checklist__error">{loadError}</p>
        <Link to="/" className="btn">홈으로</Link>
      </div>
    )
  }

  if (!trip || !items) {
    return <div className="trip-checklist"><p className="trip-checklist__hint">불러오는 중...</p></div>
  }

  const total = items.length
  const done = items.filter((item) => item.checked).length
  const percent = total === 0 ? 0 : Math.round((done / total) * 100)

  // 같은 기한(D-7, D-3 …)끼리 묶어서 보여준다
  const groups = []
  items.forEach((item) => {
    const last = groups[groups.length - 1]
    if (last && last.dueOffsetDays === item.dueOffsetDays) last.items.push(item)
    else groups.push({ dueOffsetDays: item.dueOffsetDays, dueDate: item.dueDate, items: [item] })
  })

  return (
    <div className="trip-checklist">
      <div className="trip-checklist__header">
        <div>
          <h1 className="trip-checklist__title">출발 전 체크리스트</h1>
          <p className="trip-checklist__hint">
            {trip.title} · {trip.region}
          </p>
        </div>
        <Link to={`/schedule/${trip.tripId}`} className="btn">일정 보기</Link>
      </div>

      <div className="card trip-checklist__summary">
        <p className="trip-checklist__count">
          {done}/{total} <span>완료</span>
        </p>
        <div className="trip-checklist__bar" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent}>
          <div className="trip-checklist__bar-fill" style={{ width: `${percent}%` }} />
        </div>
      </div>

      {actionError && <p className="trip-checklist__error">{actionError}</p>}

      {groups.map((group) => (
        <section key={group.dueOffsetDays} className="card trip-checklist__group">
          <h2 className="trip-checklist__group-title">
            {dueBadge(group.dueOffsetDays)}
            <span>{formatDueDate(group.dueDate)}까지</span>
          </h2>
          <ul className="trip-checklist__list">
            {group.items.map((item) => (
              <li key={item.itemId} className="trip-checklist__item">
                <label className="trip-checklist__label">
                  <input
                    type="checkbox"
                    checked={item.checked}
                    disabled={busyId === item.itemId}
                    onChange={() => handleToggle(item)}
                  />
                  <span className={item.checked ? 'trip-checklist__text trip-checklist__text--done' : 'trip-checklist__text'}>
                    {item.content}
                  </span>
                </label>
                {isOverdue(item) && <span className="trip-checklist__overdue">기한 지남</span>}
                {item.category === 'CUSTOM' && <span className="trip-checklist__tag">{CATEGORY_LABELS.CUSTOM}</span>}
                <button
                  type="button"
                  className="btn trip-checklist__remove"
                  aria-label={`${item.content} 삭제`}
                  disabled={busyId === item.itemId}
                  onClick={() => handleDelete(item)}
                >
                  삭제
                </button>
              </li>
            ))}
          </ul>
        </section>
      ))}

      {total === 0 && <p className="trip-checklist__hint">항목이 없어요. 아래에서 직접 추가해 보세요.</p>}

      <form className="card trip-checklist__add" onSubmit={handleAdd}>
        <p className="card-label">직접 추가</p>
        <div className="trip-checklist__add-row">
          <input
            type="text"
            value={content}
            maxLength={CONTENT_MAX_LENGTH}
            placeholder="예: 카메라 배터리 충전"
            onChange={(event) => setContent(event.target.value)}
          />
          <select value={dueOffsetDays} onChange={(event) => setDueOffsetDays(Number(event.target.value))} aria-label="기한">
            {DUE_OPTIONS.map((days) => (
              <option key={days} value={days}>
                {days === 0 ? '출발 당일까지' : `출발 ${days}일 전까지`}
              </option>
            ))}
          </select>
          <button type="submit" className="btn btn-primary" disabled={busyId !== null || !content.trim()}>
            추가
          </button>
        </div>
      </form>
    </div>
  )
}
