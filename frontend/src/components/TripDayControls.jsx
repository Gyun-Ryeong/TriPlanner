import { useRef, useState } from 'react'
import { addTripDay, removeLastTripDay } from '../api/trips.js'
import { TRIP_ALERTS_REFRESH_EVENT } from '../lib/tripAlertsContext.js'
import './TripDayControls.css'

// 서버가 허용하는 최대 일수 (TripService.MAX_TRIP_DAYS 와 같은 값)
const MAX_DAYS = 31

// 일정 수정 중에 여행 일수를 하루씩 늘리거나 줄이는 버튼 (2박 3일 ↔ 3박 4일).
// 늘리면 마지막 일차 뒤에 새 일차가, 줄이면 마지막 일차가 사라지고 여행 종료일도 함께 바뀐다.
// 지울 일차에 일정이 들어 있으면 화면 안에서 한 번 더 확인한 뒤에만 지운다 (서버도 확인 없이는 지우지 않는다)
export default function TripDayControls({ trip, disabled = false, onChanged }) {
  const [confirming, setConfirming] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const lock = useRef(false)

  const dayCount = trip.days.length
  const lastDay = trip.days[dayCount - 1]
  const itemCount = lastDay?.items.length ?? 0
  const locked = disabled || busy

  async function run(request) {
    if (lock.current) return
    lock.current = true
    setBusy(true)
    setError('')
    try {
      const detail = await request()
      setConfirming(false)
      onChanged(detail)
      // 종료일이 바뀌었으니 여행 알림도 다시 계산한다
      window.dispatchEvent(new Event(TRIP_ALERTS_REFRESH_EVENT))
    } catch (err) {
      // 화면에는 비어 보였지만 서버에는 일정이 있는 경우: 확인을 거쳐 지운다
      if (err.status === 409) setConfirming(true)
      else setError(err.message ?? '일차를 바꾸지 못했습니다.')
    } finally {
      lock.current = false
      setBusy(false)
    }
  }

  function handleRemoveClick() {
    setError('')
    if (itemCount === 0) run(() => removeLastTripDay(trip.tripId, false))
    else setConfirming(true)
  }

  return (
    <div className="trip-day-controls">
      <div className="trip-day-controls__buttons">
        <button
          type="button"
          className="btn btn-sm"
          disabled={locked || dayCount >= MAX_DAYS}
          title={dayCount >= MAX_DAYS ? `일정은 최대 ${MAX_DAYS}일까지 만들 수 있어요.` : undefined}
          onClick={() => run(() => addTripDay(trip.tripId))}
        >
          + {dayCount + 1}일차 추가
        </button>
        <button
          type="button"
          className="btn btn-sm"
          disabled={locked || dayCount <= 1 || confirming}
          title={dayCount <= 1 ? '일정은 최소 하루가 있어야 해요.' : undefined}
          onClick={handleRemoveClick}
        >
          − {dayCount}일차 삭제
        </button>
      </div>

      {error && <p className="trip-day-controls__error">{error}</p>}

      {confirming && (
        <div className="trip-day-controls__confirm" role="alertdialog" aria-label={`${dayCount}일차 삭제 확인`}>
          <p className="trip-day-controls__message">
            {itemCount > 0
              ? `${dayCount}일차에 등록된 일정 ${itemCount}개가 있어요. 삭제하면 일정도 함께 사라지며 되돌릴 수 없어요.`
              : `${dayCount}일차에 등록된 일정이 있어요. 삭제하면 일정도 함께 사라지며 되돌릴 수 없어요.`}
            <br />
            여행 종료일도 하루 앞당겨져요. 정말 삭제할까요?
          </p>
          <div className="trip-day-controls__confirm-buttons">
            <button
              type="button"
              className="btn trip-day-controls__danger"
              disabled={busy}
              onClick={() => run(() => removeLastTripDay(trip.tripId, true))}
            >
              {busy ? '삭제 중...' : `${dayCount}일차 삭제`}
            </button>
            <button type="button" className="btn" disabled={busy} onClick={() => setConfirming(false)}>
              취소
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
