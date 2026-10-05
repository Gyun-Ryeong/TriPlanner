import { useEffect, useReducer } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { AUTH_CHANGED_EVENT, getAuth, clearAuth } from '../api/authStorage.js'
import ChatbotWidget from './ChatbotWidget.jsx'
import './MainLayout.css'

const NAV_ITEMS = [
  { to: '/', label: '홈', end: true },
  { to: '/mytrips/stats', label: '여행 일정', end: true },
  { to: '/chatbot', label: '여행 챗봇' },
  { to: '/mytrips', label: '내 여행', end: true },
  { to: '/alerts', label: '실시간 알림' },
]

export default function MainLayout() {
  const navigate = useNavigate()
  const [, refreshAuth] = useReducer((n) => n + 1, 0)
  const auth = getAuth()

  useEffect(() => {
    window.addEventListener(AUTH_CHANGED_EVENT, refreshAuth)
    return () => window.removeEventListener(AUTH_CHANGED_EVENT, refreshAuth)
  }, [])

  function handleLogout() {
    clearAuth()
    navigate('/login')
  }

  return (
    <div className="layout">
      <header className="app-header">
        <div className="app-header__inner">
          <span className="app-header__logo">TriPlanner</span>

          <nav className="app-header__nav">
            {NAV_ITEMS.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  isActive ? 'app-header__link app-header__link--active' : 'app-header__link'
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>

          <div className="app-header__user">
            {auth ? (
              <>
                <span className="app-header__user-name">{auth.nickname}님</span>
                <button type="button" className="app-header__logout" onClick={handleLogout}>
                  로그아웃
                </button>
              </>
            ) : (
              <NavLink to="/login" className="app-header__login-link">로그인</NavLink>
            )}
          </div>
        </div>
      </header>

      <main className="app-content">
        <Outlet />
      </main>

      <footer className="app-footer">
        <div className="app-footer__inner">
          <div>
            <span className="app-footer__logo">TriPlanner</span>
            <p className="app-footer__tagline">국내 여행의 모든 순간을 더 안전하고 자유롭게</p>
          </div>
          <p className="app-footer__team">팀원 · 이동희 · 김령균 · 이시우</p>
          <p className="app-footer__copyright">© 2026 TriPlanner</p>
        </div>
      </footer>

      {auth && <ChatbotWidget />}
    </div>
  )
}
