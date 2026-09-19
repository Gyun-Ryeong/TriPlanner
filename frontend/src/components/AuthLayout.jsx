import './AuthLayout.css'

export default function AuthLayout({ children }) {
  return (
    <div className="auth-layout">
      <aside className="auth-layout__side">
        <span className="auth-layout__logo">TriPlanner</span>

        <div className="auth-layout__pitch">
          <h1>국내 여행의 모든 순간을 더 안전하고 자유롭게</h1>
          <p>
            맞춤 일정부터 실시간 여행 알림, AI 여행 상담까지. TriPlanner가 든든한 여행
            동반자가 되어드릴게요.
          </p>
        </div>

        <span className="auth-layout__copyright">© 2026 TriPlanner</span>
      </aside>

      <section className="auth-layout__main">{children}</section>
    </div>
  )
}
