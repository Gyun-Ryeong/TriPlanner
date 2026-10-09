import { useEffect, useState } from 'react'
import { getAdminUsers } from '../api/admin.js'

function formatDate(value) {
  if (!value) return '-'
  return value.slice(0, 16).replace('T', ' ')
}

export default function AdminUserList() {
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [keyword, setKeyword] = useState('')

  function fetchUsers() {
    return getAdminUsers()
      .then((data) => {
        setUsers(data)
        setError('')
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }

  function reloadUsers() {
    setLoading(true)
    fetchUsers()
  }

  useEffect(() => {
    fetchUsers()
  }, [])

  const query = keyword.trim().toLowerCase()
  const filtered = query
    ? users.filter((user) =>
        [user.email, user.nickname, user.phone].some((value) => value?.toLowerCase().includes(query)),
      )
    : users

  return (
    <section className="card admin__section">
      <div className="admin__row">
        <div>
          <h2 className="admin__heading">회원 목록</h2>
          <p className="admin__hint">
            전체 {users.length}명{query && ` · 검색 결과 ${filtered.length}명`} (최근 가입순)
          </p>
        </div>
        <div className="admin__actions">
          <input
            className="admin__search"
            type="search"
            placeholder="이메일·닉네임·전화번호 검색"
            value={keyword}
            onChange={(event) => setKeyword(event.target.value)}
          />
          <button type="button" className="btn" onClick={reloadUsers} disabled={loading}>
            새로고침
          </button>
        </div>
      </div>

      {error && <p className="admin__error">{error}</p>}

      <div className="admin__table-wrap">
        <table className="admin__table">
          <thead>
            <tr>
              <th>ID</th>
              <th>이메일(아이디)</th>
              <th>닉네임</th>
              <th>전화번호</th>
              <th>가입일</th>
              <th>여행 수</th>
              <th>여행 알림</th>
              <th>마케팅 동의</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((user) => (
              <tr key={user.userId}>
                <td>{user.userId}</td>
                <td>
                  {user.email}
                  {user.admin && <span className="badge badge-warn admin__role">관리자</span>}
                </td>
                <td>{user.nickname || '-'}</td>
                <td>{user.phone || '-'}</td>
                <td>{formatDate(user.createdAt)}</td>
                <td>{user.tripCount}</td>
                <td>{user.tripAlertsEnabled ? '켜짐' : '꺼짐'}</td>
                <td>{user.marketingConsent ? '동의' : '-'}</td>
              </tr>
            ))}
            {!loading && filtered.length === 0 && (
              <tr>
                <td colSpan={8} className="admin__empty">
                  {query ? '검색 결과가 없습니다.' : '회원이 없습니다.'}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  )
}
