import { useRef, useState } from 'react'
import { deleteTrip } from '../api/trips.js'
import './TripDeleteButton.css'

// 여행 삭제 버튼 — 누르면 화면 안에서 한 번 더 확인한 뒤 삭제한다 (일자·일정 항목도 함께 삭제됨)
export default function TripDeleteButton({ tripId, title, onDeleted }) {
  const [confirming, setConfirming] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [error, setError] = useState('')
  const lock = useRef(false)

  async function handleDelete() {
    if (lock.current) return
    lock.current = true
    setDeleting(true)
    setError('')
    try {
      await deleteTrip(tripId)
      onDeleted(tripId)
    } catch (err) {
      // 이미 다른 곳에서 삭제된 여행이면 목적은 달성된 것이므로 삭제된 것으로 처리한다
      if (err.status === 404) {
        onDeleted(tripId)
        return
      }
      setError(err.message ?? '여행을 삭제하지 못했습니다.')
      setDeleting(false)
    } finally {
      lock.current = false
    }
  }

  if (!confirming) {
    return (
      <button type="button" className="btn trip-delete__trigger" onClick={() => setConfirming(true)}>
        여행 삭제
      </button>
    )
  }

  return (
    <div className="trip-delete__confirm" role="alertdialog" aria-label={`${title} 삭제 확인`}>
      <p className="trip-delete__message">
        &lsquo;{title}&rsquo; 여행을 삭제할까요? 일정도 함께 삭제되며 되돌릴 수 없어요.
      </p>
      {error && <p className="trip-delete__error">{error}</p>}
      <div className="trip-delete__buttons">
        <button type="button" className="btn trip-delete__confirm-btn" disabled={deleting} onClick={handleDelete}>
          {deleting ? '삭제 중...' : '삭제'}
        </button>
        <button
          type="button"
          className="btn"
          disabled={deleting}
          onClick={() => {
            setConfirming(false)
            setError('')
          }}
        >
          취소
        </button>
      </div>
    </div>
  )
}
