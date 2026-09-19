import { Link } from 'react-router-dom'
import AuthLayout from '../components/AuthLayout.jsx'
import './auth-form.css'

export default function Signup() {
  return (
    <AuthLayout>
      <div className="auth-card">
        <h2>TriPlanner를 시작해볼까요?</h2>
        <p className="auth-card__subtitle">기본 정보를 입력하고 나만의 여행을 시작하세요.</p>

        <form onSubmit={(e) => e.preventDefault()}>
          <div className="auth-field">
            <label htmlFor="name">이름</label>
            <input id="name" type="text" placeholder="이민지" />
          </div>

          <div className="auth-field">
            <label htmlFor="email">이메일 주소</label>
            <input id="email" type="email" placeholder="example@triplanner.com" />
          </div>

          <div className="auth-field">
            <label htmlFor="password">비밀번호</label>
            <input id="password" type="password" placeholder="영문, 숫자 포함 8자 이상" />
          </div>

          <div className="auth-field">
            <label htmlFor="passwordConfirm">비밀번호 확인</label>
            <input id="passwordConfirm" type="password" placeholder="비밀번호를 한 번 더 입력해주세요" />
          </div>

          <button type="submit" className="auth-submit">회원가입</button>
        </form>

        <p className="auth-switch">
          이미 계정이 있으신가요? <Link to="/login">로그인</Link>
        </p>
      </div>
    </AuthLayout>
  )
}
