import { useState } from 'react'
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import AuthLayout from '../components/AuthLayout.jsx'
import { login } from '../api/auth.js'
import { saveAuth } from '../api/authStorage.js'
import { API_BASE_URL } from '../api/client.js'
import './auth-form.css'

export default function Login() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const signedUp = useLocation().state?.signedUp === true
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(searchParams.get('error') ?? '')
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
              placeholder="이메일입력"
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
              placeholder="비밀번호입력"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>

          {signedUp && !error && (
            <p className="auth-success">회원가입이 완료되었습니다. 새 계정으로 로그인해주세요.</p>
          )}
          {error && <p className="auth-error">{error}</p>}

          <button type="submit" className="auth-submit" disabled={submitting}>
            {submitting ? '로그인 중...' : '로그인'}
          </button>
        </form>

        <div className="auth-divider">또는</div>

        <a href={`${API_BASE_URL}/api/auth/naver/login`} className="auth-naver-button">
          네이버로 로그인
        </a>

        <p className="auth-switch">
          아직 회원이 아니신가요? <Link to="/signup">회원가입</Link>
        </p>
      </div>
    </AuthLayout>
  )
}
