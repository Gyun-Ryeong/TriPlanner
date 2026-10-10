import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { clearAuth, getAuth, saveAuth } from '../api/authStorage.js'
import {
  changePassword,
  getProfile,
  updateMarketingConsent,
  updateNotifications,
  updateProfile,
  withdraw,
} from '../api/profile.js'
import Toast from '../components/Toast.jsx'
import { WITHDRAWAL_RETENTION_DAYS } from '../lib/consentTexts.js'
import { formatPhone } from '../lib/phoneFormat.js'
import { TRIP_ALERTS_REFRESH_EVENT } from '../lib/tripAlertsContext.js'
import './ProfileEdit.css'

const NICKNAME_MAX = 50

export default function ProfileEdit() {
  const navigate = useNavigate()
  const auth = getAuth()
  const [nickname, setNickname] = useState(auth?.nickname ?? '')
  const [savedNickname, setSavedNickname] = useState(auth?.nickname ?? '')
  const [phone, setPhone] = useState('')
  const [savedPhone, setSavedPhone] = useState('')
  const [profileSaving, setProfileSaving] = useState(false)
  const [profileMessage, setProfileMessage] = useState(null)
  const profileLock = useRef(false)

  const [tripAlertsEnabled, setTripAlertsEnabled] = useState(true)
  const [marketingConsent, setMarketingConsent] = useState(false)
  const [notificationsSaving, setNotificationsSaving] = useState(false)
  const [notificationsMessage, setNotificationsMessage] = useState(null)
  const [toast, setToast] = useState(null)
  const clearToast = useCallback(() => setToast(null), [])
  const notificationsLock = useRef(false)

  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [newPasswordConfirm, setNewPasswordConfirm] = useState('')
  const [passwordSaving, setPasswordSaving] = useState(false)
  const [passwordMessage, setPasswordMessage] = useState(null)
  const passwordLock = useRef(false)

  const [withdrawConfirmed, setWithdrawConfirmed] = useState(false)
  const [withdrawing, setWithdrawing] = useState(false)
  const [withdrawMessage, setWithdrawMessage] = useState(null)

  useEffect(() => {
    let cancelled = false
    getProfile()
      .then((profile) => {
        if (cancelled) return
        setNickname(profile.nickname ?? '')
        setSavedNickname(profile.nickname ?? '')
        setPhone(profile.phone ?? '')
        setSavedPhone(profile.phone ?? '')
        setTripAlertsEnabled(profile.tripAlertsEnabled)
        setMarketingConsent(profile.marketingConsent)
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [])

  const trimmedNickname = nickname.trim()
  const profileDirty = trimmedNickname !== savedNickname || phone.trim() !== savedPhone

  const handleProfileSave = async (e) => {
    e.preventDefault()
    if (profileLock.current) return
    if (!trimmedNickname) {
      setProfileMessage({ type: 'error', text: '이름을 입력해 주세요.' })
      return
    }

    profileLock.current = true
    setProfileSaving(true)
    setProfileMessage(null)
    try {
      const profile = await updateProfile({ nickname: trimmedNickname, phone: phone.trim() })
      const current = getAuth()
      if (current) saveAuth({ ...current, nickname: profile.nickname })
      setNickname(profile.nickname)
      setSavedNickname(profile.nickname)
      setPhone(profile.phone ?? '')
      setSavedPhone(profile.phone ?? '')
      setProfileMessage({ type: 'success', text: '저장되었습니다.' })
    } catch (err) {
      setProfileMessage({ type: 'error', text: err.message })
    } finally {
      profileLock.current = false
      setProfileSaving(false)
    }
  }

  // 토글은 누르는 즉시 저장한다 (저장 중에는 다시 누를 수 없다)
  const handleToggleTripAlerts = async () => {
    if (notificationsLock.current) return
    notificationsLock.current = true
    setNotificationsSaving(true)
    setNotificationsMessage(null)
    try {
      const profile = await updateNotifications({ tripAlertsEnabled: !tripAlertsEnabled })
      setTripAlertsEnabled(profile.tripAlertsEnabled)
      window.dispatchEvent(new Event(TRIP_ALERTS_REFRESH_EVENT))
      // 성공 안내는 1.5초만 떴다 사라지는 토스트로, 실패는 읽을 시간이 필요하므로 아래 빨간 글씨로 남긴다
      setToast({
        id: Date.now(),
        text: profile.tripAlertsEnabled ? '여행 알림을 켰어요.' : '여행 알림을 껐어요.',
      })
    } catch (err) {
      setNotificationsMessage({ type: 'error', text: err.message })
    } finally {
      notificationsLock.current = false
      setNotificationsSaving(false)
    }
  }

  // 수신 동의·철회는 처리 결과를 이용자에게 알려야 하므로 처리 일자와 함께 토스트로 안내한다 (정보통신망법 제50조)
  const handleToggleMarketing = async () => {
    if (notificationsLock.current) return
    notificationsLock.current = true
    setNotificationsSaving(true)
    setNotificationsMessage(null)
    try {
      const profile = await updateMarketingConsent({ marketingConsent: !marketingConsent })
      setMarketingConsent(profile.marketingConsent)
      const today = new Date().toLocaleDateString('ko-KR')
      setToast({
        id: Date.now(),
        text: profile.marketingConsent
          ? `${today} 마케팅 정보 수신에 동의했어요.`
          : `${today} 마케팅 정보 수신 동의를 철회했어요.`,
      })
    } catch (err) {
      setNotificationsMessage({ type: 'error', text: err.message })
    } finally {
      notificationsLock.current = false
      setNotificationsSaving(false)
    }
  }

  const handlePasswordSave = async (e) => {
    e.preventDefault()
    if (passwordLock.current) return
    if (newPassword.length < 8) {
      setPasswordMessage({ type: 'error', text: '새 비밀번호는 8자 이상이어야 합니다.' })
      return
    }
    if (newPassword !== newPasswordConfirm) {
      setPasswordMessage({ type: 'error', text: '새 비밀번호 확인이 일치하지 않습니다.' })
      return
    }

    passwordLock.current = true
    setPasswordSaving(true)
    setPasswordMessage(null)
    try {
      await changePassword({ currentPassword, newPassword })
      setCurrentPassword('')
      setNewPassword('')
      setNewPasswordConfirm('')
      setPasswordMessage({ type: 'success', text: '비밀번호가 변경되었습니다.' })
    } catch (err) {
      setPasswordMessage({ type: 'error', text: err.message })
    } finally {
      passwordLock.current = false
      setPasswordSaving(false)
    }
  }

  const handleWithdraw = async () => {
    if (withdrawing || !withdrawConfirmed) return
    if (!window.confirm('정말 탈퇴하시겠어요? 탈퇴하면 바로 로그아웃되고 다시 로그인할 수 없습니다.')) return

    setWithdrawing(true)
    setWithdrawMessage(null)
    try {
      await withdraw()
      clearAuth()
      navigate('/login', { replace: true, state: { withdrawn: true } })
    } catch (err) {
      setWithdrawMessage({ type: 'error', text: err.message })
      setWithdrawing(false)
    }
  }

  return (
    <div className="profile-edit">
      <h1 className="profile-edit__title">프로필 수정</h1>
      <p className="profile-edit__subtitle">여행 알림과 안전 정보를 위한 기본 정보를 관리하세요.</p>

      <div className="profile-edit__grid">
        <div className="profile-edit__column">
          <form className="card" onSubmit={handleProfileSave}>
            <p className="card-label">기본 정보</p>

            <div className="profile-edit__field">
              <label htmlFor="name">이름</label>
              <input
                id="name"
                type="text"
                value={nickname}
                maxLength={NICKNAME_MAX}
                onChange={(e) => setNickname(e.target.value)}
              />
            </div>

            <div className="profile-edit__field">
              <label htmlFor="email">이메일 주소</label>
              <input id="email" type="email" value={auth?.email ?? ''} readOnly disabled />
              <p className="profile-edit__hint">이메일은 로그인 계정이라 변경할 수 없습니다.</p>
            </div>

            <div className="profile-edit__field">
              <label htmlFor="phone">전화번호</label>
              <input
                id="phone"
                type="tel"
                placeholder="010-1234-5678 (선택)"
                inputMode="numeric"
                maxLength={13}
                value={phone}
                onChange={(e) => setPhone(formatPhone(e.target.value))}
              />
            </div>

            {profileMessage && (
              <p className={`profile-edit__message profile-edit__message--${profileMessage.type}`}>
                {profileMessage.text}
              </p>
            )}

            <button
              type="submit"
              className="btn btn-primary btn-block profile-edit__save"
              disabled={profileSaving || !profileDirty}
            >
              {profileSaving ? '저장 중...' : '변경사항 저장'}
            </button>
          </form>

          <form className="card" onSubmit={handlePasswordSave}>
            <p className="card-label">비밀번호 변경</p>

            <div className="profile-edit__field">
              <label htmlFor="current-password">현재 비밀번호</label>
              <input
                id="current-password"
                type="password"
                autoComplete="current-password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
              />
            </div>

            <div className="profile-edit__field">
              <label htmlFor="new-password">새 비밀번호</label>
              <input
                id="new-password"
                type="password"
                autoComplete="new-password"
                placeholder="8자 이상"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
              />
            </div>

            <div className="profile-edit__field">
              <label htmlFor="new-password-confirm">새 비밀번호 확인</label>
              <input
                id="new-password-confirm"
                type="password"
                autoComplete="new-password"
                value={newPasswordConfirm}
                onChange={(e) => setNewPasswordConfirm(e.target.value)}
              />
            </div>

            {passwordMessage && (
              <p className={`profile-edit__message profile-edit__message--${passwordMessage.type}`}>
                {passwordMessage.text}
              </p>
            )}

            <button
              type="submit"
              className="btn btn-primary btn-block profile-edit__save"
              disabled={passwordSaving || !currentPassword || !newPassword || !newPasswordConfirm}
            >
              {passwordSaving ? '변경 중...' : '비밀번호 변경'}
            </button>
          </form>
        </div>

        <div className="card">
          <p className="card-label">알림 및 업데이트 설정</p>

          <div className="profile-edit__toggle-row">
            <div>
              <span>여행 위험 실시간 알림</span>
              <p className="profile-edit__hint profile-edit__toggle-hint">
                여행 3일 전부터 날씨·대기질·기상특보 알림을 받아요. 끄면 종 알림과 알림 목록이 표시되지 않아요.
              </p>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={tripAlertsEnabled}
              aria-label="여행 위험 실시간 알림"
              className={`toggle ${tripAlertsEnabled ? 'toggle--on' : ''}`}
              disabled={notificationsSaving}
              onClick={handleToggleTripAlerts}
            >
              <span className="toggle__thumb" />
            </button>
          </div>
          <ToggleRow label="일정 변경 및 준비 알림" />
          <div className="profile-edit__toggle-row">
            <div>
              <span>마케팅 정보 수신</span>
              <p className="profile-edit__hint profile-edit__toggle-hint">
                이벤트·신규 기능 소식을 받아요. 현재 발송 기능은 준비 중이며, 발송이 시작되면 서비스 화면으로 안내해요.
              </p>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={marketingConsent}
              aria-label="마케팅 정보 수신"
              className={`toggle ${marketingConsent ? 'toggle--on' : ''}`}
              disabled={notificationsSaving}
              onClick={handleToggleMarketing}
            >
              <span className="toggle__thumb" />
            </button>
          </div>

          {notificationsMessage && (
            <p className={`profile-edit__message profile-edit__message--${notificationsMessage.type}`}>
              {notificationsMessage.text}
            </p>
          )}
          <p className="profile-edit__hint">일정 변경 및 준비 알림은 기능 준비 중입니다.</p>
        </div>
      </div>

      <section className="card profile-edit__withdraw">
        <p className="card-label">회원 탈퇴</p>
        <ul className="profile-edit__withdraw-list">
          <li>탈퇴하면 바로 로그아웃되며 같은 계정으로 다시 로그인할 수 없습니다.</li>
          <li>
            계정 복구와 오처리 방지를 위해 탈퇴 후 {WITHDRAWAL_RETENTION_DAYS}일간 보관한 뒤, 여행 일정·챗봇 기록을 포함한
            모든 데이터를 파기합니다. 파기된 데이터는 되돌릴 수 없습니다.
          </li>
          <li>{WITHDRAWAL_RETENTION_DAYS}일 안에는 운영팀에 문의해 복구할 수 있고, 같은 이메일로 다시 가입할 수 없습니다.</li>
        </ul>

        <label className="profile-edit__withdraw-confirm">
          <input
            type="checkbox"
            checked={withdrawConfirmed}
            onChange={(e) => setWithdrawConfirmed(e.target.checked)}
          />
          <span>안내 사항을 모두 확인했으며 탈퇴에 동의합니다.</span>
        </label>

        {withdrawMessage && (
          <p className={`profile-edit__message profile-edit__message--${withdrawMessage.type}`}>
            {withdrawMessage.text}
          </p>
        )}

        <button
          type="button"
          className="btn profile-edit__withdraw-button"
          disabled={!withdrawConfirmed || withdrawing}
          onClick={handleWithdraw}
        >
          {withdrawing ? '탈퇴 처리 중...' : '회원 탈퇴'}
        </button>
      </section>
      <Toast message={toast} onClose={clearToast} />
    </div>
  )
}

function ToggleRow({ label }) {
  return (
    <div className="profile-edit__toggle-row">
      <span>{label}</span>
      <button type="button" className="toggle" disabled aria-disabled="true" aria-label={`${label} (준비 중)`}>
        <span className="toggle__thumb" />
      </button>
    </div>
  )
}
