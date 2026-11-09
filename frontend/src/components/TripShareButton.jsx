import { useEffect, useRef, useState } from 'react'
import { disableTripSharing, enableTripSharing } from '../api/shared.js'
import './TripShareButton.css'

function shareUrl(shareCode) {
  return `${window.location.origin}/shared/${shareCode}`
}

// 일정 화면의 '공유' 버튼: 읽기 전용 링크를 만들고, 복사하고, 필요하면 공유를 멈춘다
// compact: 여행 목록 카드 안에서 쓸 때 (설명 패널이 위쪽으로 열린다). onChange: 공유 코드가 바뀔 때마다 알려 준다
export default function TripShareButton({ tripId, initialShareCode, compact = false, onChange }) {
  const [shareCode, setShareCode] = useState(initialShareCode ?? null)
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [copied, setCopied] = useState(false)
  const wrapRef = useRef(null)
  const inputRef = useRef(null)
  const copiedTimer = useRef(null)

  // 다른 곳을 누르거나 Esc 를 누르면 닫는다
  useEffect(() => {
    if (!open) return undefined
    const onPointer = (event) => {
      if (wrapRef.current && !wrapRef.current.contains(event.target)) setOpen(false)
    }
    const onKey = (event) => {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onPointer)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onPointer)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  useEffect(() => () => clearTimeout(copiedTimer.current), [])

  async function handleCreate() {
    setBusy(true)
    setError('')
    try {
      const result = await enableTripSharing(tripId)
      setShareCode(result.shareCode)
      onChange?.(result.shareCode)
    } catch (err) {
      setError(err.message ?? '공유 링크를 만들지 못했어요.')
    } finally {
      setBusy(false)
    }
  }

  async function handleStop() {
    setBusy(true)
    setError('')
    try {
      await disableTripSharing(tripId)
      setShareCode(null)
      setCopied(false)
      onChange?.(null)
    } catch (err) {
      setError(err.message ?? '공유를 중지하지 못했어요.')
    } finally {
      setBusy(false)
    }
  }

  async function handleCopy() {
    const url = shareUrl(shareCode)
    let ok = false
    try {
      await navigator.clipboard.writeText(url)
      ok = true
    } catch {
      // 클립보드 권한이 없으면 입력칸을 선택해 복사를 시도한다
      inputRef.current?.select()
      try {
        ok = document.execCommand('copy')
      } catch {
        ok = false
      }
    }
    if (ok) {
      setCopied(true)
      clearTimeout(copiedTimer.current)
      copiedTimer.current = setTimeout(() => setCopied(false), 2000)
    } else {
      setError('자동 복사가 안 돼요. 링크를 길게 눌러 직접 복사해 주세요.')
    }
  }

  return (
    <div className={`trip-share${compact ? ' trip-share--compact' : ''}`} ref={wrapRef}>
      <button
        type="button"
        className={`btn btn-sm${shareCode ? ' trip-share__trigger--on' : ''}`}
        aria-expanded={open}
        onClick={() => setOpen((prev) => !prev)}
      >
        🔗 공유{shareCode ? ' 중' : ''}
      </button>

      {open && (
        <div className="card trip-share__panel" role="dialog" aria-label="일정 공유">
          {shareCode ? (
            <>
              <p className="trip-share__title">공유 링크</p>
              <div className="trip-share__row">
                <input
                  ref={inputRef}
                  className="trip-share__input"
                  readOnly
                  value={shareUrl(shareCode)}
                  onFocus={(event) => event.target.select()}
                />
                <button type="button" className="btn btn-primary btn-sm" onClick={handleCopy}>
                  {copied ? '복사됨 ✓' : '복사'}
                </button>
              </div>
              <p className="trip-share__note">
                링크를 아는 사람은 로그인 없이 이 일정을 볼 수 있어요. 보기만 가능하고 수정할 수 없으며,
                체크리스트와 알림은 보이지 않아요.
              </p>
              <button type="button" className="trip-share__stop" disabled={busy} onClick={handleStop}>
                공유 중지
              </button>
            </>
          ) : (
            <>
              <p className="trip-share__title">이 일정을 링크로 공유할까요?</p>
              <p className="trip-share__note">
                링크를 받은 사람은 로그인 없이 일정을 볼 수 있어요(수정 불가). 카카오톡이나 DM으로 링크를 보내 주세요.
                언제든 공유를 중지하면 링크가 바로 막혀요.
              </p>
              <button type="button" className="btn btn-primary btn-sm" disabled={busy} onClick={handleCreate}>
                {busy ? '만드는 중…' : '공유 링크 만들기'}
              </button>
            </>
          )}
          {error && <p className="trip-share__error">{error}</p>}
        </div>
      )}
    </div>
  )
}
