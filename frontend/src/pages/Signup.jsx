import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import AuthLayout from '../components/AuthLayout.jsx'
import { signup } from '../api/auth.js'
import { saveAuth } from '../api/authStorage.js'
import './auth-form.css'

export default function Signup() {
  const navigate = useNavigate()
  const [nickname, setNickname] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [passwordConfirm, setPasswordConfirm] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')

    if (password !== passwordConfirm) {
      setError('비밀번호가 일치하지 않습니다.')
      return
    }

    setSubmitting(true)
    try {
      const auth = await signup({ email, password, nickname })
      saveAuth(auth)
      navigate('/')
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
            <label htmlFor="name">이름</label>
            <input
              id="name"
              type="text"
              placeholder="이민지"
              value={nickname}
              onChange={(e) => setNickname(e.target.value)}
              required
            />
          </div>

          <div className="auth-field">
            <label htmlFor="email">이메일 주소</label>
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
            <label htmlFor="password">비밀번호</label>
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
            <label htmlFor="passwordConfirm">비밀번호 확인</label>
            <input
              id="passwordConfirm"
              type="password"
              placeholder="비밀번호를 한 번 더 입력해주세요"
              value={passwordConfirm}
              onChange={(e) => setPasswordConfirm(e.target.value)}
              required
            />
          </div>

          {error && <p className="auth-error">{error}</p>}

          <button type="submit" className="auth-submit" disabled={submitting}>
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
