import { useRef, useState } from 'react'
import { deleteTrip } from '../api/trips.js'
import { TrashIcon } from './Icons.jsx'
import './TripDeleteButton.css'

// 여행 삭제 버튼 — 누르면 화면 안에서 한 번 더 확인한 뒤 삭제한다 (일자·일정 항목도 함께 삭제됨)
export default function TripDeleteButton({ tripId, title, onDeleted, compact = false }) {
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
    // compact: 여행 목록 카드처럼 자리가 좁은 곳에서는 휴지통 아이콘만 보여준다
    if (compact) {
      return (
        <button
          type="button"
          className="btn btn-sm trip-delete__trigger trip-delete__trigger--icon"
          aria-label={`${title} 여행 삭제`}
          title="여행 삭제"
          onClick={() => setConfirming(true)}
        >
          <TrashIcon size={16} />
        </button>
      )
    }
    return (
      <button type="button" className="btn trip-delete__trigger" onClick={() => setConfirming(true)}>
        여행 삭제
      </button>
    )
  }

  // 박스 없이 한 줄: "삭제할까요?  삭제 · 취소" (일정도 함께 지워지고 되돌릴 수 없다는 점은 짧게 안내)
  return (
    <div className="trip-delete__confirm" role="alertdialog" aria-label={`${title} 삭제 확인`}>
      <span className="trip-delete__message">일정도 함께 삭제돼요. 삭제할까요?</span>
      <button type="button" className="trip-delete__link trip-delete__link--danger" disabled={deleting} onClick={handleDelete}>
        {deleting ? '삭제 중…' : '삭제'}
      </button>
      <button
        type="button"
        className="trip-delete__link"
        disabled={deleting}
        onClick={() => {
          setConfirming(false)
          setError('')
        }}
      >
        취소
      </button>
      {error && <span className="trip-delete__error">{error}</span>}
    </div>
  )
}
