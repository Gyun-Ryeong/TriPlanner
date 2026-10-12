import { useEffect, useState } from 'react'
import { clearChatbotErrors, getChatbotErrors } from '../api/admin.js'
import './AdminChatbotErrors.css'

// 서버는 분류를 코드로 내려주고, 화면에 보이는 이름은 여기서만 정한다
const CATEGORIES = [
  ['CONNECTION', '챗봇 서버 연결 실패'],
  ['TIMEOUT', '응답 시간 초과'],
  ['AI_MODEL', 'AI 모델 연결 실패'],
  ['SERVER_ERROR', '챗봇 서버 오류'],
  ['BAD_REQUEST', '요청 오류'],
  ['OTHER', '기타'],
]
const CATEGORY_LABEL = Object.fromEntries(CATEGORIES)

function formatDateTime(value) {
  return value ? value.slice(0, 19).replace('T', ' ') : '-'
}

// 관리자 페이지의 '챗봇 오류 기록': 사용자가 챗봇을 쓰다 만난 오류를 분류별로 모아 보여준다 (30일 보관)
export default function AdminChatbotErrors() {
  const [category, setCategory] = useState('')
  const [data, setData] = useState({ total: 0, counts: {}, items: [] })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  function fetchErrors(selected) {
    setLoading(true)
    return getChatbotErrors(selected)
      .then((response) => {
        setData(response)
        setError('')
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    fetchErrors(category)
  }, [category])

  async function handleClear() {
    if (!window.confirm('챗봇 오류 기록을 모두 삭제할까요? 되돌릴 수 없어요.')) return
    try {
      await clearChatbotErrors()
      await fetchErrors(category)
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <section className="card admin__section">
      <div className="admin__row">
        <div>
          <h2 className="admin__heading">챗봇 오류 기록</h2>
          <p className="admin__hint">
            사용자가 챗봇을 쓰다 만난 오류를 분류별로 보여줍니다. 30일이 지난 기록은 자동으로 지워지고, 목록은 최근 50건입니다.
          </p>
        </div>
        <div className="admin__actions">
          <button type="button" className="btn" onClick={() => fetchErrors(category)} disabled={loading}>
            새로고침
          </button>
          <button type="button" className="btn" onClick={handleClear} disabled={loading || data.total === 0}>
            전체 삭제
          </button>
        </div>
      </div>

      <div className="chatbot-errors__chips" role="group" aria-label="오류 분류">
        <button
          type="button"
          className={`chatbot-errors__chip${category === '' ? ' chatbot-errors__chip--active' : ''}`}
          aria-pressed={category === ''}
          onClick={() => setCategory('')}
        >
          전체 <strong>{data.total}</strong>
        </button>
        {CATEGORIES.map(([code, label]) => (
          <button
            key={code}
            type="button"
            className={`chatbot-errors__chip${category === code ? ' chatbot-errors__chip--active' : ''}`}
            aria-pressed={category === code}
            onClick={() => setCategory(code)}
          >
            {label} <strong>{data.counts[code] ?? 0}</strong>
          </button>
        ))}
      </div>

      {error && <p className="admin__error">{error}</p>}

      <div className="admin__table-wrap">
        <table className="admin__table chatbot-errors__table">
          <thead>
            <tr>
              <th>발생 시각</th>
              <th>사용자</th>
              <th>분류</th>
              <th>상태</th>
              <th>원인</th>
              <th>질문(앞 100자)</th>
            </tr>
          </thead>
          <tbody>
            {data.items.map((item) => (
              <tr key={item.errorId}>
                <td>{formatDateTime(item.createdAt)}</td>
                <td>{item.email ? `${item.email}${item.nickname ? ` (${item.nickname})` : ''}` : '-'}</td>
                <td>
                  <span className="badge badge-danger">{CATEGORY_LABEL[item.category] ?? item.category}</span>
                </td>
                <td>{item.httpStatus ?? '-'}</td>
                <td className="chatbot-errors__text" title={item.detail ?? ''}>{item.detail || '-'}</td>
                <td className="chatbot-errors__text" title={item.queryPreview ?? ''}>{item.queryPreview || '-'}</td>
              </tr>
            ))}
            {!loading && data.items.length === 0 && (
              <tr>
                <td colSpan={6} className="admin__empty">
                  {category ? '이 분류의 오류 기록이 없습니다.' : '챗봇 오류 기록이 없습니다.'}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  )
}
