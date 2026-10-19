import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getAuth } from '../api/authStorage.js'
import { getMyTrips } from '../api/trips.js'
import { CalendarIcon, MapIcon, PinIcon, PlaneIcon, PlusIcon } from '../components/Icons.jsx'
import TripDeleteButton from '../components/TripDeleteButton.jsx'
import { tripPhoto } from '../lib/regionPhotos.js'
import { placeLabel } from '../lib/tripPlace.js'
import './TripStats.css'

function formatDateRange(startDate, endDate) {
  const start = new Date(startDate)
  const end = new Date(endDate)
  const startLabel = `${start.getFullYear()}.${String(start.getMonth() + 1).padStart(2, '0')}.${String(start.getDate()).padStart(2, '0')}`
  const endLabel = `${String(end.getMonth() + 1).padStart(2, '0')}.${String(end.getDate()).padStart(2, '0')}`
  return `${startLabel} - ${endLabel}`
}

function tripDays(startDate, endDate) {
  const start = new Date(startDate)
  const end = new Date(endDate)
  return Math.round((end - start) / (1000 * 60 * 60 * 24)) + 1
}

function localToday() {
  const now = new Date()
  const pad = (n) => String(n).padStart(2, '0')
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`
}

// 목록 필터: 끝나지 않은 여행(종료일이 오늘 이후)을 '다가오는 여행', 끝난 여행을 '지난 여행'으로 본다
const FILTERS = [
  { key: 'all', label: '전체', match: () => true },
  { key: 'upcoming', label: '다가오는 여행', match: (trip, today) => trip.endDate >= today },
  { key: 'past', label: '지난 여행', match: (trip, today) => trip.endDate < today },
]

export default function TripStats() {
  const auth = getAuth()
  const [trips, setTrips] = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('all')

  useEffect(() => {
    let cancelled = false

    getMyTrips()
      .then((data) => {
        if (!cancelled) setTrips(data)
      })
      .catch(() => {
        if (!cancelled) setTrips([])
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [])

  const regionCount = new Set(trips.map((t) => t.region)).size
  const totalDays = trips.reduce((sum, t) => sum + tripDays(t.startDate, t.endDate), 0)

  const today = localToday()
  const activeFilter = FILTERS.find((f) => f.key === filter)
  const visibleTrips = trips.filter((t) => activeFilter.match(t, today))

  return (
    <div className="trip-stats">
      <div className="page-head">
        <div>
          <p className="page-eyebrow">MY TRAVEL LOG</p>
          <h1 className="page-title">여행 통계</h1>
          <p className="page-subtitle">{auth?.nickname ?? '내'}님의 국내 여행 기록을 한눈에 확인하세요.</p>
        </div>
        <Link to="/trips/new" className="btn btn-primary">
          <PlusIcon size={16} /> 새 여행 생성하기
        </Link>
      </div>

      <div className="trip-stats__summary">
        <div className="card trip-stats__stat">
          <span className="trip-stats__stat-icon trip-stats__stat-icon--blue"><PlaneIcon size={22} /></span>
          <div>
            <p className="card-label">총 여행 횟수</p>
            <p className="trip-stats__summary-main">{loading ? '-' : trips.length}<span>회</span></p>
          </div>
        </div>
        <div className="card trip-stats__stat">
          <span className="trip-stats__stat-icon trip-stats__stat-icon--green"><PinIcon size={22} /></span>
          <div>
            <p className="card-label">방문한 지역</p>
            <p className="trip-stats__summary-main">{loading ? '-' : regionCount}<span>곳</span></p>
          </div>
        </div>
        <div className="card trip-stats__stat">
          <span className="trip-stats__stat-icon trip-stats__stat-icon--orange"><CalendarIcon size={22} /></span>
          <div>
            <p className="card-label">누적 여행 일수</p>
            <p className="trip-stats__summary-main">{loading ? '-' : totalDays}<span>일</span></p>
          </div>
        </div>
      </div>

      <div className="card trip-stats__list-card">
        <div className="card-head">
          <h2 className="card-title">여행 목록</h2>
          <div className="trip-stats__tabs" role="tablist" aria-label="여행 목록 필터">
            {FILTERS.map((f) => (
              <button
                key={f.key}
                type="button"
                role="tab"
                aria-selected={filter === f.key}
                className={`trip-stats__tab${filter === f.key ? ' trip-stats__tab--active' : ''}`}
                onClick={() => setFilter(f.key)}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>

        {loading && <p className="trip-stats__place-desc">불러오는 중...</p>}

        {!loading && visibleTrips.length === 0 && (
          <div className="empty-state">
            <span className="empty-state__icon"><MapIcon size={24} /></span>
            <p className="empty-state__title">
              {trips.length === 0 ? '아직 등록된 여행이 없어요' : `${activeFilter.label} 목록이 비어 있어요`}
            </p>
            <p className="empty-state__desc">
              {trips.length === 0
                ? '첫 여행을 만들면 일정과 통계가 여기에 쌓여요.'
                : '다른 탭에서 전체 여행을 확인해 보세요.'}
            </p>
            {trips.length === 0 && (
              <Link to="/trips/new" className="btn btn-primary btn-sm">
                <PlusIcon size={14} /> 새 여행 생성하기
              </Link>
            )}
          </div>
        )}

        {visibleTrips.length > 0 && (
          <div className="trip-stats__grid">
            {visibleTrips.map((t) => (
              <div key={t.tripId} className="trip-stats__place">
                <Link to={`/schedule/${t.tripId}`} className="trip-stats__link">
                  <div className="trip-stats__photo" aria-hidden="true">
                    {tripPhoto(t) && <img src={tripPhoto(t)} alt="" loading="lazy" />}
                  </div>
                  <div className="trip-stats__place-body">
                    <div className="trip-stats__place-header">
                      <p className="trip-stats__place-name">{t.title}</p>
                      <span className="trip-stats__place-date">{formatDateRange(t.startDate, t.endDate)}</span>
                    </div>
                    <p className="trip-stats__place-desc">{placeLabel(t)}</p>
                  </div>
                </Link>
                <div className="trip-stats__place-actions">
                  <TripDeleteButton
                    tripId={t.tripId}
                    title={t.title}
                    onDeleted={(id) => setTrips((prev) => prev.filter((trip) => trip.tripId !== id))}
                  />
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
