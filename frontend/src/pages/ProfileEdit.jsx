import { useState } from 'react'
import './ProfileEdit.css'

export default function ProfileEdit() {
  const [notifications, setNotifications] = useState({
    risk: true,
    schedule: true,
    marketing: false,
  })

  const toggle = (key) =>
    setNotifications((prev) => ({ ...prev, [key]: !prev[key] }))

  return (
    <div className="profile-edit">
      <h1 className="profile-edit__title">프로필 수정</h1>
      <p className="profile-edit__subtitle">여행 알림과 안전 정보를 위한 기본 정보를 관리하세요.</p>

      <div className="profile-edit__grid">
        <div className="card">
          <p className="card-label">기본 정보</p>

          <div className="profile-edit__field">
            <label htmlFor="name">이름</label>
            <input id="name" type="text" defaultValue="이민지" />
          </div>

          <div className="profile-edit__field">
            <label htmlFor="email">이메일 주소</label>
            <input id="email" type="email" defaultValue="minji.lee@triplanner.com" />
          </div>

          <div className="profile-edit__field">
            <label htmlFor="phone">전화번호</label>
            <input id="phone" type="tel" defaultValue="010-1234-5678" />
          </div>
        </div>

        <div className="card">
          <p className="card-label">알림 및 업데이트 설정</p>

          <ToggleRow
            label="여행 위험 실시간 알림"
            checked={notifications.risk}
            onChange={() => toggle('risk')}
          />
          <ToggleRow
            label="일정 변경 및 준비 알림"
            checked={notifications.schedule}
            onChange={() => toggle('schedule')}
          />
          <ToggleRow
            label="마케팅 정보 수신"
            checked={notifications.marketing}
            onChange={() => toggle('marketing')}
          />

          <button type="button" className="btn btn-primary btn-block profile-edit__save">
            변경사항 저장
          </button>
        </div>
      </div>
    </div>
  )
}

function ToggleRow({ label, checked, onChange }) {
  return (
    <div className="profile-edit__toggle-row">
      <span>{label}</span>
      <button
        type="button"
        className={checked ? 'toggle toggle--on' : 'toggle'}
        onClick={onChange}
        aria-pressed={checked}
      >
        <span className="toggle__thumb" />
      </button>
    </div>
  )
}
