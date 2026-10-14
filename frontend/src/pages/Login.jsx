import { useState } from 'react'
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import AuthLayout from '../components/AuthLayout.jsx'
import { login } from '../api/auth.js'
import { saveAuth } from '../api/authStorage.js'
import { API_BASE_URL } from '../api/client.js'
import './auth-form.css'

const SOCIAL_PREVIEW = [
  {
    key: 'kakao',
    label: '카카오',
    className: 'auth-social__btn--kakao',
    icon: (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path
          fill="#191919"
          d="M12 3C6.48 3 2 6.58 2 11c0 2.86 1.88 5.37 4.7 6.78l-.95 3.5c-.08.3.26.54.52.36l4.16-2.76c.52.07 1.04.12 1.57.12 5.52 0 10-3.58 10-8s-4.48-8-10-8z"
        />
      </svg>
    ),
  },
  {
    key: 'google',
    label: '구글',
    className: 'auth-social__btn--google',
    icon: (
      <svg viewBox="0 0 48 48" aria-hidden="true">
        <path fill="#4285F4" d="M45.12 24.5c0-1.56-.14-3.06-.4-4.5H24v8.51h11.84c-.51 2.75-2.06 5.08-4.39 6.64v5.52h7.11c4.16-3.83 6.56-9.47 6.56-16.17z" />
        <path fill="#34A853" d="M24 46c5.94 0 10.92-1.97 14.56-5.33l-7.11-5.52c-1.97 1.32-4.49 2.1-7.45 2.1-5.73 0-10.58-3.87-12.31-9.07H4.34v5.7C7.96 41.07 15.4 46 24 46z" />
        <path fill="#FBBC05" d="M11.69 28.18C11.25 26.86 11 25.45 11 24s.25-2.86.69-4.18v-5.7H4.34C2.85 17.09 2 20.45 2 24c0 3.55.85 6.91 2.34 9.88l7.35-5.7z" />
        <path fill="#EA4335" d="M24 10.75c3.23 0 6.13 1.11 8.41 3.29l6.31-6.31C34.91 4.18 29.93 2 24 2 15.4 2 7.96 6.93 4.34 14.12l7.35 5.7c1.73-5.2 6.58-9.07 12.31-9.07z" />
      </svg>
    ),
  },
  {
    key: 'apple',
    label: '애플',
    className: 'auth-social__btn--apple',
    icon: (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path
          fill="#fff"
          d="M12.152 6.896c-.948 0-2.415-1.078-3.96-1.04-2.04.027-3.91 1.183-4.961 3.014-2.117 3.675-.546 9.103 1.519 12.09 1.013 1.454 2.208 3.09 3.792 3.039 1.52-.065 2.09-.987 3.935-.987 1.831 0 2.35.987 3.96.948 1.637-.026 2.676-1.48 3.676-2.948 1.156-1.688 1.636-3.325 1.662-3.415-.039-.013-3.182-1.221-3.22-4.857-.026-3.04 2.48-4.494 2.597-4.559-1.429-2.09-3.623-2.324-4.39-2.376-2-.156-3.675 1.09-4.61 1.09zM15.53 3.83c.843-1.012 1.4-2.427 1.245-3.83-1.207.052-2.662.805-3.532 1.818-.78.896-1.454 2.338-1.273 3.714 1.338.104 2.715-.688 3.559-1.701"
        />
      </svg>
    ),
  },
]

export default function Login() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const location = useLocation()
  const signedUp = location.state?.signedUp === true
  const withdrawn = location.state?.withdrawn === true
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(searchParams.get('error') ?? '')
  const [submitting, setSubmitting] = useState(false)
  const [socialNotice, setSocialNotice] = useState('')

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
        <p className="auth-card__eyebrow">WELCOME BACK</p>
        <h2>다시 만나 반가워요</h2>
        <p className="auth-card__subtitle">계정에 로그인해 여행 계획을 이어가세요.</p>

        <form onSubmit={handleSubmit}>
          <div className="auth-field">
            <label htmlFor="email">이메일 주소</label>
            {/* 관리자 아이디(test)는 이메일 형식이 아니라서 type="email" 대신 text 를 쓴다 */}
            <input
              id="email"
              type="text"
              inputMode="email"
              autoComplete="username"
              placeholder="name@example.com"
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
              placeholder="비밀번호를 입력해주세요"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>

          {signedUp && !error && (
            <p className="auth-success">회원가입이 완료되었습니다. 새 계정으로 로그인해주세요.</p>
          )}
          {withdrawn && !error && (
            <p className="auth-success">회원 탈퇴가 완료되었습니다. 그동안 TriPlanner를 이용해 주셔서 감사합니다.</p>
          )}
          {error && <p className="auth-error">{error}</p>}

          <button type="submit" className="auth-submit" disabled={submitting}>
            {submitting ? '로그인 중...' : '로그인'}
          </button>
        </form>

        <div className="auth-divider">SNS 계정으로 간편 로그인</div>

        {/* 네이버만 실제로 연동돼 있고, 나머지는 화면용(누르면 준비 중 안내) */}
        <div className="auth-social">
          <a
            href={`${API_BASE_URL}/api/auth/naver/login`}
            className="auth-social__btn auth-social__btn--naver"
            aria-label="네이버로 로그인"
            title="네이버"
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path fill="#fff" d="M16.27 12.85 7.38 3H3v18h4.73v-9.85L16.62 21H21V3h-4.73z" />
            </svg>
          </a>
          {SOCIAL_PREVIEW.map(({ key, label, className, icon }) => (
            <button
              key={key}
              type="button"
              className={`auth-social__btn ${className}`}
              aria-label={`${label}로 로그인`}
              title={label}
              onClick={() => setSocialNotice(`${label} 로그인은 준비 중이에요.`)}
            >
              {icon}
            </button>
          ))}
        </div>
        {socialNotice && <p className="auth-social__notice">{socialNotice}</p>}

        <p className="auth-switch">
          아직 회원이 아니신가요? <Link to="/signup">회원가입</Link>
        </p>
      </div>
    </AuthLayout>
  )
}
