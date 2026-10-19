import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getAuth } from '../api/authStorage.js'
import { getProfile } from '../api/profile.js'
import { getMyTrips } from '../api/trips.js'
import { MailIcon, PencilIcon, PhoneIcon, PlaneIcon, PlusIcon } from '../components/Icons.jsx'
import { TripAlertBlock, upcomingAlertsMessage } from '../components/TripAlertList.jsx'
import { useTripAlerts } from '../lib/tripAlertsContext.js'
import { pickUpcomingTrip } from '../lib/upcomingTrip.js'
import { placeLabel } from '../lib/tripPlace.js'
import './MyTrips.css'

function formatDate(dateString) {
  const date = new Date(dateString)
  return `${date.getFullYear()}. ${date.getMonth() + 1}. ${date.getDate()}`
}

function localToday() {
  const now = new Date()
  const pad = (n) => String(n).padStart(2, '0')
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`
}

export default function MyTrips() {
  const auth = getAuth()
  const [trips, setTrips] = useState([])
  const [phone, setPhone] = useState('')
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

    // 전화번호는 로그인 정보에 없어서 프로필에서 따로 받아온다 (못 받아도 화면에는 영향 없음)
    getProfile()
      .then((profile) => {
        if (!cancelled) setPhone(profile.phone ?? '')
      })
      .catch(() => {})

    return () => {
      cancelled = true
    }
  }, [])

  const regionCount = new Set(trips.map((t) => t.region)).size
  const pastCount = trips.filter((t) => t.endDate < localToday()).length
  const upcomingTrip = pickUpcomingTrip(trips)
  const upcomingAlerts = upcomingTrip
    ? alertData?.trips.find((t) => t.tripId === upcomingTrip.tripId)
    : null
  const name = auth?.nickname ?? '알 수 없음'

  return (
    <div className="mytrips">
      <div className="page-head">
        <div>
          <p className="page-eyebrow">MY PAGE</p>
          <h1 className="page-title">내 프로필</h1>
          <p className="page-subtitle">개인 정보와 예정된 여행의 위험 정보를 한눈에 관리하세요.</p>
        </div>
      </div>

      <div className="mytrips__grid">
        <div className="card mytrips__profile">
          <span className="mytrips__avatar" aria-hidden="true">{name.slice(0, 1)}</span>
          <div className="mytrips__profile-body">
            <p className="mytrips__name">
              {name}
              <span className="badge badge-info">{auth?.admin ? '관리자' : '여행자'}</span>
            </p>
            {auth?.email && (
              <p className="mytrips__contact"><MailIcon size={15} /> {auth.email}</p>
            )}
            {phone && (
              <p className="mytrips__contact"><PhoneIcon size={15} /> {phone}</p>
            )}
          </div>
          <Link to="/mytrips/edit" className="btn btn-primary btn-sm mytrips__edit">
            <PencilIcon size={14} /> 프로필 수정
          </Link>
        </div>

        <Link to="/mytrips/stats" className="card mytrips__stats-card">
          <h2 className="card-title">여행 통계</h2>
          <div className="mytrips__stat-tiles">
            <div className="mytrips__stat-tile">
              <p className="mytrips__stat-label">다녀온 여행</p>
              <p className="mytrips__stats-main">{loading ? '-' : pastCount}<span>번</span></p>
            </div>
            <div className="mytrips__stat-tile">
              <p className="mytrips__stat-label">방문 지역</p>
              <p className="mytrips__stats-main">{loading ? '-' : regionCount}<span>곳</span></p>
            </div>
          </div>
        </Link>
      </div>

      <div className="card mytrips__risk">
        <div className="card-head">
          <h2 className="card-title">다가오는 여행</h2>
          {!loading && upcomingTrip && <Link to="/alerts" className="card-link">알림 전체 보기 →</Link>}
        </div>
        {loading ? (
          <p className="mytrips__meta">불러오는 중...</p>
        ) : upcomingTrip ? (
          <div className="mytrips__risk-body">
            <p className="mytrips__risk-title">{upcomingTrip.title}</p>
            <p className="mytrips__meta mytrips__risk-meta">{placeLabel(upcomingTrip)} · {formatDate(upcomingTrip.startDate)}</p>
            {upcomingAlerts ? (
              <TripAlertBlock trip={upcomingAlerts} />
            ) : (
              <p className="mytrips__meta">{upcomingAlertsMessage(upcomingTrip, alertData, alertLoading)}</p>
            )}
          </div>
        ) : (
          <div className="empty-state">
            <span className="empty-state__icon"><PlaneIcon size={24} /></span>
            <p className="empty-state__title">예정된 여행이 없어요</p>
            <p className="empty-state__desc">첫 여행지를 골라 일정을 만들어보세요.</p>
            <Link to="/trips/new" className="btn btn-primary btn-sm">
              <PlusIcon size={14} /> 새 여행 생성하기
            </Link>
          </div>
        )}
      </div>
    </div>
  )
}
