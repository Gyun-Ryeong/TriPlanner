import { useEffect, useState } from 'react'
import { getTripNews } from '../api/trips.js'
import './TripNewsCards.css'

// 여행지 소식 카드 (여행 일정 화면·알림 탭). 두 칸으로 나눠 본다.
//   지역 소식 : 축제·관광 등 여행 관련 소식 먼저
//   사건사고  : 여행에 영향을 주는 이슈(통제·침수·특보, '주의') 먼저, 그다음 화재·교통사고·사건
// 사진은 기사 원문의 대표 사진(미리보기용)이고, 없으면 그 지역 대표 사진이다.
const TABS = [
  { id: 'local', label: '지역 소식', empty: '최근 이 지역 소식을 찾지 못했어요.' },
  { id: 'incident', label: '사건사고', empty: '최근 두 달 안에 알아둘 만한 사건·사고가 없어요.' },
]

export default function TripNewsCards({ tripId, heading, limit = 6 }) {
  const [state, setState] = useState({ loading: true, data: null, error: false })
  const [tab, setTab] = useState('local')

  useEffect(() => {
    if (!tripId) return undefined
    const controller = new AbortController()
    setState({ loading: true, data: null, error: false })
    getTripNews(tripId, controller.signal)
      .then((data) => setState({ loading: false, data, error: false }))
      .catch((error) => {
        if (error.name !== 'AbortError') setState({ loading: false, data: null, error: true })
      })
    return () => controller.abort()
  }, [tripId])

  const all = state.data?.items ?? []
  const groups = {
    // 예전 응답(group 없음)도 보이게: 이슈는 사건사고, 나머지는 지역 소식
    local: all.filter((item) => (item.group ?? (item.kind === 'issue' ? 'incident' : 'local')) === 'local').slice(0, limit),
    incident: all.filter((item) => (item.group ?? (item.kind === 'issue' ? 'incident' : 'local')) === 'incident').slice(0, limit),
  }
  const issueCount = groups.incident.filter((item) => item.kind === 'issue').length
  const label = state.data?.label
  const failed = !state.loading && (state.error || state.data?.unavailable)
  const current = TABS.find((t) => t.id === tab)
  const items = groups[tab]

  return (
    <section className="trip-news" aria-label="여행지 소식">
      <div className="trip-news__head">
        <h2 className="trip-news__title">{heading ?? (label ? `${label} 소식` : '여행지 소식')}</h2>
        {label && heading && <span className="trip-news__label">{label} 기준</span>}
      </div>

      {!state.loading && !failed && (
        <div className="trip-news__tabs" role="tablist" aria-label="소식 종류">
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              role="tab"
              aria-selected={tab === t.id}
              className={`trip-news__tab${tab === t.id ? ' trip-news__tab--active' : ''}`}
              onClick={() => setTab(t.id)}
            >
              {t.label} <span className="trip-news__count">{groups[t.id].length}</span>
              {/* 여행에 영향을 주는 이슈가 있으면 다른 탭을 보고 있어도 눈에 띄게 */}
              {t.id === 'incident' && issueCount > 0 && <span className="trip-news__tab-alert">주의 {issueCount}</span>}
            </button>
          ))}
        </div>
      )}

      {state.loading && <p className="trip-news__note">여행지 소식을 모으고 있어요…</p>}
      {failed && <p className="trip-news__note">지금은 여행지 소식을 불러오지 못했어요. 잠시 뒤에 다시 확인해 주세요.</p>}
      {!state.loading && !failed && items.length === 0 && <p className="trip-news__note">{current.empty}</p>}

      {!state.loading && !failed && items.length > 0 && (
        <ul className="trip-news__grid" role="tabpanel">
          {items.map((item, index) => (
            <li key={`${item.title}-${index}`}>
              <NewsCard item={item} />
            </li>
          ))}
        </ul>
      )}

      {all.length > 0 && (
        <p className="trip-news__footnote">
          기사 사진은 원문 미리보기이며 저작권은 각 언론사에 있습니다. 사진이 없는 기사는 지역 대표 사진으로 보여 드려요.
          {tab === 'incident' && ' 사건사고는 최근 두 달 기사 중 이 지역에서 일어난 것만 골랐어요.'}
        </p>
      )}
    </section>
  )
}

// 원문 주소가 없는 기사(연합뉴스 재난 기사 일부)는 받은 본문을 창으로 보여 준다
function ArticleDialog({ item, onClose }) {
  useEffect(() => {
    const onKey = (event) => {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div className="trip-news__overlay" role="presentation" onClick={onClose}>
      <div
        className="trip-news__dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="trip-news-dialog-title"
        onClick={(event) => event.stopPropagation()}
      >
        <button type="button" className="trip-news__dialog-close" aria-label="닫기" onClick={onClose}>
          ✕
        </button>
        <p className="trip-news__dialog-meta">{[item.date, item.source].filter(Boolean).join(' · ')}</p>
        <h3 id="trip-news-dialog-title" className="trip-news__dialog-title">{item.title}</h3>
        <div className="trip-news__dialog-body">
          {item.body.split('\n').map((paragraph, index) => (
            <p key={index}>{paragraph}</p>
          ))}
        </div>
        <p className="trip-news__dialog-credit">출처: {item.credit || item.source}</p>
      </div>
    </div>
  )
}

function NewsCard({ item }) {
  const [imageFailed, setImageFailed] = useState(false)
  const [open, setOpen] = useState(false)
  const issue = item.kind === 'issue'
  const incident = item.kind === 'incident'
  const showImage = item.image && !imageFailed

  const body = (
    <>
      <div className={`trip-news__thumb${item.image_is_fallback ? ' trip-news__thumb--region' : ''}`}>
        {showImage ? (
          <img
            src={item.image}
            alt=""
            loading="lazy"
            referrerPolicy="no-referrer"
            onError={() => setImageFailed(true)}
          />
        ) : (
          <span className="trip-news__thumb-empty" aria-hidden="true">📰</span>
        )}
        {issue && <span className="trip-news__badge">주의{item.category ? ` · ${item.category}` : ''}</span>}
        {incident && item.category && <span className="trip-news__badge trip-news__badge--incident">{item.category}</span>}
      </div>
      <div className="trip-news__text">
        <p className="trip-news__card-title">{item.title}</p>
        {item.summary && <p className="trip-news__summary">{item.summary}</p>}
        <p className="trip-news__meta">
          {[item.date, item.source].filter(Boolean).join(' · ')}
          {item.link && <span className="trip-news__more">원문 보기 →</span>}
          {!item.link && item.body && <span className="trip-news__more">본문 보기 →</span>}
        </p>
      </div>
    </>
  )

  const className = `trip-news__card${issue ? ' trip-news__card--issue' : ''}`
  if (item.link) {
    return (
      <a className={className} href={item.link} target="_blank" rel="noopener noreferrer">
        {body}
      </a>
    )
  }
  if (item.body) {
    return (
      <>
        <button type="button" className={`${className} trip-news__card--button`} onClick={() => setOpen(true)}>
          {body}
        </button>
        {open && <ArticleDialog item={item} onClose={() => setOpen(false)} />}
      </>
    )
  }
  return <div className={className}>{body}</div>
}
