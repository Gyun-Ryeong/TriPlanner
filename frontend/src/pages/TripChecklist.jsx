import { useEffect, useLayoutEffect, useState } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'
import {
  addChecklistItem,
  deleteChecklistItem,
  getChecklist,
  getTrip,
  setChecklistItemChecked,
} from '../api/trips.js'
import { getAuth } from '../api/authStorage.js'
import { prepAlertKey, useDismissedAlerts } from '../lib/dismissedAlerts.js'
import { CATEGORY_LABELS, dueBadge, dueOptionsFor, formatDueDate, relevantItems } from '../lib/checklist.js'
import './TripChecklist.css'

const CONTENT_MAX_LENGTH = 100

export default function TripChecklist() {
  const { tripId } = useParams()
  const navigate = useNavigate()
  // 새 여행을 만든 직후 '다음'으로 넘어온 경우: 기본 항목을 정리하는 단계로 보여준다
  const setup = useLocation().state?.setup === true
  const { dismiss } = useDismissedAlerts(getAuth()?.userId)
  const [trip, setTrip] = useState(null)
  const [items, setItems] = useState(null)
  const [loadError, setLoadError] = useState('')
  const [actionError, setActionError] = useState('')
  const [busyId, setBusyId] = useState(null)
  const [content, setContent] = useState('')
  const [dueOffsetDays, setDueOffsetDays] = useState(1)

  // 정리하는 동안에는 '오늘까지인 항목' 알림이 종에 쌓이지 않게 지워 둔다 (다음 날 새로 기한이 되는 항목은 다시 알려준다)
  useLayoutEffect(() => {
    if (setup) dismiss([prepAlertKey({ tripId }, { kind: 'CHECKLIST' })])
  }, [setup, tripId, dismiss])

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

  // 고른 기한이 이미 지난 값이면(출발이 가까운 여행) 고를 수 있는 가장 이른 기한으로 바꿔 쓴다
  function selectedDue(tripData) {
    const options = dueOptionsFor(tripData.startDate)
    return options.includes(dueOffsetDays) ? dueOffsetDays : options[0]
  }

  function handleAdd(event) {
    event.preventDefault()
    const text = content.trim()
    if (!text) return
    return run('add', async () => {
      const created = await addChecklistItem(tripId, { content: text, dueOffsetDays: selectedDue(trip) })
      setItems((prev) =>
        [...prev, created].sort((a, b) => b.dueOffsetDays - a.dueOffsetDays || a.itemId - b.itemId)
      )
      setContent('')
    })
  }

  function finishSetup() {
    navigate(`/schedule/${tripId}`, { replace: true })
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

  // 기한이 이미 지난 미완료 항목(예: 출발 6일 전의 D-7 항목)은 보여주지 않는다
  const shown = relevantItems(items)
  const total = shown.length
  const done = shown.filter((item) => item.checked).length
  const percent = total === 0 ? 0 : Math.round((done / total) * 100)

  // 같은 기한(D-7, D-3 …)끼리 묶어서 보여준다
  const groups = []
  shown.forEach((item) => {
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
        {setup ? (
          <button type="button" className="btn btn-primary" onClick={finishSetup}>완료</button>
        ) : (
          <Link to={`/schedule/${trip.tripId}`} className="btn">일정 보기</Link>
        )}
      </div>

      {setup && (
        <p className="card trip-checklist__setup-guide">
          출발 전에 챙길 기본 항목을 미리 만들어 두었어요. 필요 없는 항목은 삭제하고, 더 필요한 항목은 아래에서 추가해 보세요.
          다 정리했으면 &lsquo;완료&rsquo;를 눌러 일정을 확인하세요.
        </p>
      )}

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

      {total === 0 && (
        <p className="trip-checklist__hint">
          {items.length > 0 ? '지금 준비할 항목이 없어요. 필요하면 아래에서 추가해 보세요.' : '항목이 없어요. 아래에서 직접 추가해 보세요.'}
        </p>
      )}

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
          <select value={selectedDue(trip)} onChange={(event) => setDueOffsetDays(Number(event.target.value))} aria-label="기한">
            {dueOptionsFor(trip.startDate).map((days) => (
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

      {setup && (
        <div className="trip-checklist__setup-footer">
          <button type="button" className="btn btn-primary" onClick={finishSetup}>완료</button>
        </div>
      )}
    </div>
  )
}
