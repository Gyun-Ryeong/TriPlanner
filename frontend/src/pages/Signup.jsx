import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import AuthLayout from '../components/AuthLayout.jsx'
import { signup } from '../api/auth.js'
import { CONSENT_ITEMS, CONSENT_NOTE, EMPTY_CONSENTS } from '../lib/consentTexts.js'
import { formatPhone } from '../lib/phoneFormat.js'
import './auth-form.css'

export default function Signup() {
  const navigate = useNavigate()
  const [nickname, setNickname] = useState('')
  const [email, setEmail] = useState('')
  const [phone, setPhone] = useState('')
  const [password, setPassword] = useState('')
  const [passwordConfirm, setPasswordConfirm] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [consents, setConsents] = useState(EMPTY_CONSENTS)
  const [openConsent, setOpenConsent] = useState(null)

  const requiredAgreed = CONSENT_ITEMS.every((item) => !item.required || consents[item.key])
  const allChecked = CONSENT_ITEMS.every((item) => consents[item.key])

  function handleToggleAll(e) {
    setConsents(Object.fromEntries(CONSENT_ITEMS.map((item) => [item.key, e.target.checked])))
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')

    if (password !== passwordConfirm) {
      setError('비밀번호가 일치하지 않습니다.')
      return
    }
    if (!requiredAgreed) {
      setError('필수 약관에 동의해 주세요.')
      return
    }

    setSubmitting(true)
    try {
      await signup({ email, password, nickname, phone: phone.trim(), consents })
      navigate('/login', { state: { signedUp: true } })
    } catch (err) {
      setError(err.message ?? '회원가입에 실패했습니다.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <AuthLayout>
      <div className="auth-card">
        <h2>TriPlanner를 시작해볼까요?</h2>
        <p className="auth-card__subtitle">기본 정보를 입력하고 나만의 여행을 시작하세요.</p>

        <form onSubmit={handleSubmit}>
          <div className="auth-field">
            <label htmlFor="name">이름<span className="auth-required" aria-hidden="true">*</span></label>
            <input
              id="name"
              type="text"
              placeholder="닉네임 입력"
              value={nickname}
              onChange={(e) => setNickname(e.target.value)}
              required
            />
          </div>

          <div className="auth-field">
            <label htmlFor="email">이메일 주소<span className="auth-required" aria-hidden="true">*</span></label>
            <input
              id="email"
              type="email"
              placeholder="example@triplanner.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>

          <div className="auth-field">
            <label htmlFor="phone">전화번호 (선택)</label>
            <input
              id="phone"
              type="tel"
              placeholder="010-1234-5678"
              inputMode="numeric"
              maxLength={13}
              value={phone}
              onChange={(e) => setPhone(formatPhone(e.target.value))}
            />
          </div>

          <div className="auth-field">
            <label htmlFor="password">비밀번호<span className="auth-required" aria-hidden="true">*</span></label>
            <input
              id="password"
              type="password"
              placeholder="영문, 숫자 포함 8자 이상"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>

          <div className="auth-field">
            <label htmlFor="passwordConfirm">비밀번호 확인<span className="auth-required" aria-hidden="true">*</span></label>
            <input
              id="passwordConfirm"
              type="password"
              placeholder="비밀번호를 한 번 더 입력해주세요"
              value={passwordConfirm}
              onChange={(e) => setPasswordConfirm(e.target.value)}
              required
            />
          </div>

          <fieldset className="auth-consent">
            <legend className="auth-consent__legend">약관 동의</legend>

            <label className="auth-consent__all">
              <input type="checkbox" checked={allChecked} onChange={handleToggleAll} />
              <span>전체 동의 (선택 항목 포함)</span>
            </label>

            {CONSENT_ITEMS.map((item) => (
              <div key={item.key} className="auth-consent__item">
                <div className="auth-consent__row">
                  <label>
                    <input
                      type="checkbox"
                      checked={consents[item.key]}
                      onChange={(e) => setConsents((prev) => ({ ...prev, [item.key]: e.target.checked }))}
                    />
                    <span className={`auth-consent__tag ${item.required ? 'auth-consent__tag--required' : ''}`}>
                      {item.required ? '필수' : '선택'}
                    </span>
                    <span>{item.label}</span>
                  </label>
                  <button
                    type="button"
                    className="auth-consent__view"
                    aria-expanded={openConsent === item.key}
                    onClick={() => setOpenConsent((prev) => (prev === item.key ? null : item.key))}
                  >
                    {openConsent === item.key ? '접기' : '보기'}
                  </button>
                </div>
                {openConsent === item.key && <p className="auth-consent__text">{item.text}</p>}
              </div>
            ))}

            <p className="auth-consent__note">{CONSENT_NOTE}</p>
          </fieldset>

          {error && <p className="auth-error">{error}</p>}

          <button type="submit" className="auth-submit" disabled={submitting || !requiredAgreed}>
            {submitting ? '가입 중...' : '회원가입'}
          </button>
        </form>

        <p className="auth-switch">
          이미 계정이 있으신가요? <Link to="/login">로그인</Link>
        </p>
      </div>
    </AuthLayout>
  )
}
