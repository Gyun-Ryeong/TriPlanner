import { NavLink, Outlet } from 'react-router-dom'
import './MainLayout.css'

const NAV_ITEMS = [
  { to: '/', label: '홈', end: true },
  { to: '/schedule', label: '여행 일정' },
  { to: '/chatbot', label: '여행 챗봇' },
  { to: '/mytrips', label: '내 여행' },
  { to: '/alerts', label: '실시간 알림' },
]

const CURRENT_USER = {
  name: '이민지',
  email: 'minji.lee@triplanner.com',
}

export default function MainLayout() {
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
            <span className="app-header__user-name">{CURRENT_USER.name}님</span>
          </div>
        </div>
      </header>

      <main className="app-content">
        <Outlet />
      </main>
    </div>
  )
}
