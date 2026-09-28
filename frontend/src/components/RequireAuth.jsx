import { Navigate, Outlet } from 'react-router-dom'
import { getAuth } from '../api/authStorage.js'

export default function RequireAuth() {
  const auth = getAuth()

  if (!auth) {
    return <Navigate to="/login" replace />
  }

  return <Outlet />
}
