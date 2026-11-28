import { getAuth } from '../api/authStorage.js'
import AdminUserList from '../components/AdminUserList.jsx'
import './Admin.css'

// 관리자: 회원 목록 확인과 탈퇴 회원 복구만 한다
export default function Admin() {
  return (
    <div className="admin">
      <h1 className="admin__title">관리자</h1>
      <p className="admin__subtitle">{getAuth()?.email} 계정으로 접속 중</p>

      <AdminUserList />
    </div>
  )
}
