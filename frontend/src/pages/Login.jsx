import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import AuthLayout from '../components/AuthLayout.jsx'
import { login } from '../api/auth.js'
import { saveAuth } from '../api/authStorage.js'
import './auth-form.css'

export default function Login() {
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setSubmitting(true)

    try {
      const auth = await login({ email, password })
      saveAuth(auth)
      navigate('/')
    } catch (err) {
      setError(err.message ?? '로그인에 실패했습니다.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <AuthLayout>
      <div className="auth-card">
        <h2>다시 만나 반가워요</h2>
        <p className="auth-card__subtitle">계정에 로그인해 여행 계획들을 이어가세요.</p>

        <form onSubmit={handleSubmit}>
          <div className="auth-field">
            <label htmlFor="email">이메일 주소</label>
            <input
              id="email"
              type="email"
              placeholder="minji.lee@triplanner.com"
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
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>

          {error && <p className="auth-error">{error}</p>}

          <button type="submit" className="auth-submit" disabled={submitting}>
            {submitting ? '로그인 중...' : '로그인'}
          </button>
        </form>

        <p className="auth-switch">
          아직 회원이 아니신가요? <Link to="/signup">회원가입</Link>
        </p>
      </div>
    </AuthLayout>
  )
}
