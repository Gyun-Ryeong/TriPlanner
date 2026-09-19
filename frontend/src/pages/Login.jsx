import { Link } from 'react-router-dom'
import AuthLayout from '../components/AuthLayout.jsx'
import './auth-form.css'

export default function Login() {
  return (
    <AuthLayout>
      <div className="auth-card">
        <h2>다시 만나 반가워요</h2>
        <p className="auth-card__subtitle">계정에 로그인해 여행 계획들을 이어가세요.</p>

        <form onSubmit={(e) => e.preventDefault()}>
          <div className="auth-field">
            <label htmlFor="email">이메일 주소</label>
            <input id="email" type="email" placeholder="minji.lee@triplanner.com" />
          </div>

          <div className="auth-field">
            <label htmlFor="password">비밀번호</label>
            <input id="password" type="password" placeholder="••••••••" />
          </div>

          <button type="submit" className="auth-submit">로그인</button>
        </form>

        <p className="auth-switch">
          아직 회원이 아니신가요? <Link to="/signup">회원가입</Link>
        </p>
      </div>
    </AuthLayout>
  )
}
