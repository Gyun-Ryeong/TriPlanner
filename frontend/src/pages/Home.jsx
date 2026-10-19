import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getAuth } from '../api/authStorage.js'
import { getMyTrips } from '../api/trips.js'
import ChecklistCard from '../components/ChecklistCard.jsx'
import { BellIcon, BotIcon, CalendarIcon, PlaneIcon, PlusIcon } from '../components/Icons.jsx'
import { PrepAlertsSection, TripAlertsOverview, TripAlertSummary, upcomingAlertsMessage } from '../components/TripAlertList.jsx'
import { useTripAlerts } from '../lib/tripAlertsContext.js'
import { pickUpcomingTrip } from '../lib/upcomingTrip.js'
import './Home.css'

function formatUpcomingDate(startDate, endDate) {
  const start = new Date(startDate)
  const end = new Date(endDate)
  const nights = Math.round((end - start) / (1000 * 60 * 60 * 24))
  const startLabel = `${start.getFullYear()}. ${start.getMonth() + 1}. ${start.getDate()}`
  const endLabel = `${end.getMonth() + 1}. ${end.getDate()}`
  return `${startLabel} — ${endLabel} · ${nights}박 ${nights + 1}일`
}

// 홈 가운데의 바로가기 3칸
const SHORTCUTS = [
  { to: '/chatbot', title: '여행 챗봇', desc: 'AI에게 코스·맛집 추천 받기', Icon: BotIcon, tone: 'blue' },
  { to: '/mytrips/stats', title: '내 여행', desc: '저장한 일정과 동선 관리', Icon: CalendarIcon, tone: 'blue' },
  { to: '/alerts', title: '실시간 알림', desc: '권역별 날씨와 기상특보', Icon: BellIcon, tone: 'orange' },
]

export default function Home() {
  const auth = getAuth()
  const [upcomingTrip, setUpcomingTrip] = useState(null)
  const [loadingTrip, setLoadingTrip] = useState(true)
  const { data: alertData, prep: prepAlerts, loading: alertLoading, error: alertError } = useTripAlerts()
  const upcomingAlerts = upcomingTrip
    ? alertData?.trips.find((t) => t.tripId === upcomingTrip.tripId)
    : null

  useEffect(() => {
    if (!auth) {
      setLoadingTrip(false)
      return
    }

    let cancelled = false

    getMyTrips()
      .then((trips) => {
        if (!cancelled) setUpcomingTrip(pickUpcomingTrip(trips))
      })
      .catch(() => {
        if (!cancelled) setUpcomingTrip(null)
      })
      .finally(() => {
        if (!cancelled) setLoadingTrip(false)
      })

    return () => {
      cancelled = true
    }
  }, [auth])

  if (!auth) {
    return (
      <div className="home">
        <div className="home__banner home__banner--guest">
          <div className="home__banner-body">
            <p className="home__banner-greeting">로그인이 필요해요</p>
            <h1 className="home__banner-title">로그인하고 나만의 여행을 계획해보세요</h1>
            <p className="home__banner-desc">
              여행 일정 생성, AI 챗봇, 실시간 알림 등 모든 기능은 로그인 후 이용하실 수 있어요.
            </p>
            <div className="home__banner-actions">
              <Link to="/login" className="home__banner-button">로그인하기</Link>
              <Link to="/signup" className="home__banner-button home__banner-button--ghost">회원가입하기</Link>
            </div>
          </div>
          <RouteArt />
        </div>
      </div>
    )
  }

  return (
    <div className="home">
      <div className="home__banner">
        <div className="home__banner-body">
          <p className="home__banner-greeting">안녕하세요, {auth.nickname}님</p>
          <h1 className="home__banner-title">오늘도 설레는 여행을 준비해요</h1>
          <p className="home__banner-desc">
            가고 싶은 지역을 고르고, 챗봇과 일정을 짜고, 출발 전 날씨와 특보까지 한 번에 확인하세요.
          </p>
          <div className="home__banner-actions">
            <Link to="/trips/new" className="home__banner-button">
              <PlusIcon size={16} /> 새 여행 생성하기
            </Link>
          </div>
        </div>
      </div>

      <div className="home__shortcuts">
        {SHORTCUTS.map(({ to, title, desc, Icon, tone }) => (
          <Link key={to} to={to} className="home__shortcut">
            <span className={`home__shortcut-icon home__shortcut-icon--${tone}`}>
              <Icon size={20} />
            </span>
            <span>
              <span className="home__shortcut-title">{title}</span>
              <span className="home__shortcut-desc">{desc}</span>
            </span>
          </Link>
        ))}
      </div>

      <div className="home__stats">
        <div className="card">
          <div className="card-head">
            <h2 className="card-title">다가오는 여행</h2>
            <Link to="/mytrips/stats" className="card-link">전체 보기</Link>
          </div>
          {loadingTrip ? (
            <p className="home__stat-sub">불러오는 중...</p>
          ) : upcomingTrip ? (
            <>
              <Link to={`/schedule/${upcomingTrip.tripId}`} className="home__trip-link">
                <p className="home__stat-main">{upcomingTrip.title}</p>
                <p className="home__stat-sub">
                  {upcomingTrip.region} · {formatUpcomingDate(upcomingTrip.startDate, upcomingTrip.endDate)}
                </p>
              </Link>
              <div className="home__safety">
                <p className="home__safety-label">여행 임박 알림</p>
                {upcomingAlerts ? (
                  <TripAlertSummary trip={upcomingAlerts} />
                ) : (
                  <p className="home__stat-sub">{upcomingAlertsMessage(upcomingTrip, alertData, alertLoading)}</p>
                )}
              </div>
            </>
          ) : (
            <div className="empty-state">
              <span className="empty-state__icon"><PlaneIcon size={22} /></span>
              <p className="empty-state__title">아직 예정된 여행이 없어요</p>
              <p className="empty-state__desc">첫 여행지를 골라 일정을 만들어보세요.</p>
              <Link to="/trips/new" className="btn btn-primary btn-sm">
                <PlusIcon size={14} /> 새 여행 생성하기
              </Link>
            </div>
          )}
        </div>

        <ChecklistCard trip={upcomingTrip} loading={loadingTrip} />
      </div>

      <div className="home__panels">
        <div className="card">
          <div className="card-head">
            <h2 className="card-title">실시간 여행 알림</h2>
            <Link to="/alerts" className="card-link">알림 전체 보기</Link>
          </div>
          <div className="home__alert-body">
            <TripAlertsOverview data={alertData} loading={alertLoading} error={alertError} />
            <PrepAlertsSection prep={prepAlerts} />
          </div>
        </div>
      </div>
    </div>
  )
}

// 배너 오른쪽의 점선 경로와 핀 장식
function RouteArt() {
  return (
    <svg className="home__banner-art" viewBox="0 0 280 170" fill="none" aria-hidden="true">
      <path
        d="M14 150 C 60 120, 90 128, 130 110 S 190 70, 214 46"
        stroke="rgba(255,255,255,0.55)"
        strokeWidth="3"
        strokeLinecap="round"
        strokeDasharray="1 9"
      />
      <circle cx="14" cy="150" r="9" fill="#fff" />
      <circle cx="14" cy="150" r="4" fill="#2f5fe0" />
      <circle cx="170" cy="82" r="8" fill="rgba(255,255,255,0.78)" />
      <path
        d="M236 4c-17 0-30 13-30 30 0 22 30 50 30 50s30-28 30-50c0-17-13-30-30-30Z"
        fill="#fff"
      />
      <circle cx="236" cy="34" r="11" fill="#2f5fe0" />
    </svg>
  )
}
