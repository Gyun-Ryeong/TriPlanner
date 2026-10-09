import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getAdminStatus } from '../api/admin.js'
import { getAuth } from '../api/authStorage.js'
import { setDevMode, useRagChat } from '../chat/chatStore.js'
import AdminUserList from '../components/AdminUserList.jsx'
import './Admin.css'

export default function Admin() {
  const { devMode } = useRagChat()
  const [status, setStatus] = useState({ loading: true, chatbotServerUp: false, error: '' })

  function fetchStatus() {
    return getAdminStatus()
      .then((data) => setStatus({ loading: false, chatbotServerUp: data.chatbotServerUp, error: '' }))
      .catch((error) => setStatus({ loading: false, chatbotServerUp: false, error: error.message }))
  }

  function reloadStatus() {
    setStatus((prev) => ({ ...prev, loading: true, error: '' }))
    fetchStatus()
  }

  useEffect(() => {
    fetchStatus()
  }, [])

  let serverBadge = <span className="badge badge-info">확인 중</span>
  if (!status.loading) {
    serverBadge = status.chatbotServerUp
      ? <span className="badge badge-safe">정상</span>
      : <span className="badge badge-danger">연결 안 됨</span>
  }

  return (
    <div className="admin">
      <h1 className="admin__title">관리자</h1>
      <p className="admin__subtitle">{getAuth()?.email} 계정으로 접속 중</p>

      <section className="card admin__section">
        <div className="admin__row">
          <div>
            <h2 className="admin__heading">챗봇 서버 (rag_project)</h2>
            <p className="admin__hint">FastAPI 서버(기본 http://localhost:8000) 연결 상태</p>
          </div>
          <div className="admin__actions">
            {serverBadge}
            <button type="button" className="btn" onClick={reloadStatus} disabled={status.loading}>
              다시 확인
            </button>
          </div>
        </div>
        {status.error && <p className="admin__error">{status.error}</p>}
        {!status.loading && !status.chatbotServerUp && !status.error && (
          <p className="admin__hint">
            rag_project 폴더에서 <code>python -m uvicorn api_server:app --port 8000</code> 으로 실행하세요.
          </p>
        )}
      </section>

      <section className="card admin__section">
        <div className="admin__row">
          <div>
            <h2 className="admin__heading">챗봇 개발자 모드</h2>
            <p className="admin__hint">
              켜면 챗봇 답변 아래에 API 오류·제약사항, 단계별 소요 시간, AI 속도가 표시됩니다. 관리자 계정에서만 보이고,
              이 브라우저에만 적용됩니다.
            </p>
          </div>
          <label className="admin__switch">
            <input type="checkbox" checked={devMode} onChange={(event) => setDevMode(event.target.checked)} />
            <span>{devMode ? '켜짐' : '꺼짐'}</span>
          </label>
        </div>
        {devMode && (
          <p className="admin__hint">
            새로 받는 답변부터 적용됩니다. <Link to="/chatbot">여행 챗봇에서 확인하기 →</Link>
          </p>
        )}
      </section>

      <AdminUserList />
    </div>
  )
}
