import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getAuth } from '../api/authStorage.js'
import { getMyTrips } from '../api/trips.js'
import { TripAlertBlock, upcomingAlertsMessage } from '../components/TripAlertList.jsx'
import { useTripAlerts } from '../lib/tripAlertsContext.js'
import { pickUpcomingTrip } from '../lib/upcomingTrip.js'
import './MyTrips.css'

function formatDate(dateString) {
  const date = new Date(dateString)
  return `${date.getFullYear()}. ${date.getMonth() + 1}. ${date.getDate()}`
}

export default function MyTrips() {
  const auth = getAuth()
  const [trips, setTrips] = useState([])
  const [loading, setLoading] = useState(true)
  const { data: alertData, loading: alertLoading } = useTripAlerts()

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
  const upcomingTrip = pickUpcomingTrip(trips)
  const upcomingAlerts = upcomingTrip
    ? alertData?.trips.find((t) => t.tripId === upcomingTrip.tripId)
    : null

  return (
    <div className="mytrips">
      <div className="mytrips__header">
        <div>
          <h1 className="mytrips__title">내 프로필</h1>
          <p className="mytrips__subtitle">개인 정보와 예정된 여행의 위험 정보를 한눈에 관리하세요.</p>
        </div>
        <Link to="/mytrips/edit" className="btn btn-primary">프로필 수정</Link>
      </div>

      <div className="mytrips__grid">
        <div className="card">
          <p className="card-label">기본 정보</p>
          <p className="mytrips__name">{auth?.nickname ?? '알 수 없음'}</p>
          <p className="mytrips__meta">{auth?.email ?? ''}</p>
        </div>

        <Link to="/mytrips/stats" className="card mytrips__stats-card">
          <p className="card-label">여행 통계</p>
          <p className="mytrips__stats-main">{loading ? '-' : `${trips.length}번의 여행`}</p>
          <p className="mytrips__meta">{loading ? '' : `방문 지역 ${regionCount}`}</p>
        </Link>
      </div>

      <div className="card mytrips__risk">
        <div className="mytrips__risk-head">
          <p className="card-label">다가오는 여행 위험 관리</p>
          {!loading && upcomingTrip && <Link to="/alerts" className="mytrips__risk-more">알림 전체 보기 →</Link>}
        </div>
        {loading ? (
          <p className="mytrips__meta">불러오는 중...</p>
        ) : upcomingTrip ? (
          <div className="mytrips__risk-body">
            <p className="mytrips__risk-title">{upcomingTrip.title}</p>
            <p className="mytrips__meta mytrips__risk-meta">{upcomingTrip.region} · {formatDate(upcomingTrip.startDate)}</p>
            {upcomingAlerts ? (
              <TripAlertBlock trip={upcomingAlerts} />
            ) : (
              <p className="mytrips__meta">{upcomingAlertsMessage(upcomingTrip, alertData, alertLoading)}</p>
            )}
          </div>
        ) : (
          <p className="mytrips__meta">예정된 여행이 없어요.</p>
        )}
      </div>
    </div>
  )
}
