import { Navigate, Outlet } from 'react-router-dom'
import { getAuth } from '../api/authStorage.js'

// 관리자 메뉴 접근 제한 (화면용). 관리자 API 는 서버에서도 따로 막는다
export default function RequireAdmin() {
  const auth = getAuth()

  if (!auth) {
    return <Navigate to="/login" replace />
  }
  if (!auth.admin) {
    return <Navigate to="/" replace />
  }

  return <Outlet />
}
