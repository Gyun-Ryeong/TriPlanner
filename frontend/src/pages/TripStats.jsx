import { useEffect, useState } from 'react'
import { getAuth } from '../api/authStorage.js'
import { getMyTrips } from '../api/trips.js'
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

export default function TripStats() {
  const auth = getAuth()
  const [trips, setTrips] = useState([])
  const [loading, setLoading] = useState(true)

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

  return (
    <div className="trip-stats">
      <h1 className="trip-stats__title">여행 통계</h1>
      <p className="trip-stats__subtitle">{auth?.nickname ?? '내'}님의 국내 여행 기록</p>

      <div className="trip-stats__summary">
        <div className="card">
          <p className="card-label">총 여행 횟수</p>
          <p className="trip-stats__summary-main">{loading ? '-' : trips.length}<span>회</span></p>
        </div>
        <div className="card">
          <p className="card-label">방문한 지역</p>
          <p className="trip-stats__summary-main">{loading ? '-' : regionCount}<span>곳</span></p>
        </div>
        <div className="card">
          <p className="card-label">누적 여행 일수</p>
          <p className="trip-stats__summary-main">{loading ? '-' : totalDays}<span>일</span></p>
        </div>
      </div>

      <h2 className="trip-stats__section-title">여행 목록</h2>
      <div className="trip-stats__grid">
        {loading && <p className="trip-stats__place-desc">불러오는 중...</p>}
        {!loading && trips.length === 0 && <p className="trip-stats__place-desc">아직 등록된 여행이 없어요.</p>}
        {trips.map((t) => (
          <div key={t.tripId} className="trip-stats__place card">
            <div className="trip-stats__photo" aria-hidden="true" />
            <div className="trip-stats__place-body">
              <div className="trip-stats__place-header">
                <p className="trip-stats__place-name">{t.title}</p>
                <span className="trip-stats__place-date">{formatDateRange(t.startDate, t.endDate)}</span>
              </div>
              <p className="trip-stats__place-desc">{t.region}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
