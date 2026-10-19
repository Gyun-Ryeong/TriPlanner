import { Link } from 'react-router-dom'
import { PinIcon } from './Icons.jsx'
import './AuthLayout.css'

// 로그인·회원가입 공통 화면: 왼쪽은 배경 이미지 + 소개 문구, 오른쪽은 폼 카드.
// 배경 사진은 frontend/public/images/auth-bg.jpg (Ref/샘플1), 없으면 그라데이션만 보인다
export default function AuthLayout({ children }) {
  return (
    <div className="auth-layout">
      <aside className="auth-layout__side">
        <Link to="/" className="auth-layout__brand">
          <span className="auth-layout__brand-mark">
            <PinIcon size={18} />
          </span>
          <span className="auth-layout__brand-name">TriPlanner</span>
        </Link>

        <div className="auth-layout__pitch">
          <span className="auth-layout__pill">국내 여행을 더 쉽고 자유롭게</span>
          <h1>
            떠나고 싶은 순간,
            <br />
            여행은 이미 시작됩니다
          </h1>
          <p>
            맞춤 일정부터 실시간 여행 알림, AI 여행 상담까지.{' '}
            <br />
            복잡한 준비는 덜고 설렘에만 집중하세요.
          </p>
        </div>

        <span className="auth-layout__copyright">© 2026 TriPlanner</span>
      </aside>

      <section className="auth-layout__main">{children}</section>
    </div>
  )
}
