import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getAuth } from '../api/authStorage.js'
import { getMyTrips } from '../api/trips.js'
import './Home.css'

function formatUpcomingDate(startDate, endDate) {
  const start = new Date(startDate)
  const end = new Date(endDate)
  const nights = Math.round((end - start) / (1000 * 60 * 60 * 24))
  const startLabel = `${start.getFullYear()}. ${start.getMonth() + 1}. ${start.getDate()}`
  const endLabel = `${end.getMonth() + 1}. ${end.getDate()}`
  return `${startLabel} — ${endLabel} · ${nights}박 ${nights + 1}일`
}

export default function Home() {
  const auth = getAuth()
  const [upcomingTrip, setUpcomingTrip] = useState(null)
  const [loadingTrip, setLoadingTrip] = useState(true)

  useEffect(() => {
    if (!auth) {
      setLoadingTrip(false)
      return
    }

    let cancelled = false

    getMyTrips()
      .then((trips) => {
        if (!cancelled) setUpcomingTrip(trips[0] ?? null)
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
        <div className="home__hero home__hero--guest">
          <div>
            <p className="home__hero-greeting home__hero-greeting--guest">로그인이 필요해요</p>
            <h1 className="home__hero-title">로그인하고 나만의 여행을 계획해보세요</h1>
          </div>
          <Link to="/login" className="btn btn-primary">로그인하기</Link>
        </div>

        <div className="card home__guest-card">
          <p className="home__guest-text">
            여행 일정 생성, AI 챗봇, 실시간 알림 등 모든 기능은 로그인 후 이용하실 수 있어요.
          </p>
          <Link to="/signup" className="btn btn-block">회원가입하기</Link>
        </div>
      </div>
    )
  }

  return (
    <div className="home">
      <div className="home__hero">
        <div>
          <p className="home__hero-greeting">안녕하세요, {auth.nickname}님</p>
          <h1 className="home__hero-title">오늘도 설레는 여행을 준비해요</h1>
        </div>
        <Link to="/trips/new" className="btn btn-primary">+ 새 여행 생성하기</Link>
      </div>

      <div className="home__stats">
        <div className="card">
          <p className="card-label">다가오는 여행</p>
          {loadingTrip ? (
            <p className="home__stat-sub">불러오는 중...</p>
          ) : upcomingTrip ? (
            <>
              <p className="home__stat-main">{upcomingTrip.region}</p>
              <p className="home__stat-sub">{formatUpcomingDate(upcomingTrip.startDate, upcomingTrip.endDate)}</p>
              <div className="home__safety">
                <p className="home__safety-label">여행 안전 지수</p>
                <p className="home__safety-value">준비 중</p>
                <p className="home__stat-sub">이 여행의 실시간 안전 정보 기능은 준비 중입니다.</p>
              </div>
            </>
          ) : (
            <>
              <p className="home__stat-main">예정된 여행 없음</p>
              <p className="home__stat-sub">
                <Link to="/trips/new">새 여행을 만들어보세요</Link>
              </p>
            </>
          )}
        </div>

        <div className="card">
          <p className="card-label">체크리스트</p>
          <p className="home__stat-main home__stat-main--accent">준비 중</p>
          <p className="home__stat-sub">출발 전 체크리스트 기능은 준비 중입니다.</p>
        </div>
      </div>

      <div className="home__panels">
        <div className="card">
          <h3 className="home__panel-title">실시간 여행 알림</h3>
          <p className="home__alert-item">여행지의 날씨와 안전 신호를 확인해보세요.</p>
          <Link to="/alerts" className="btn btn-block">알림 전체 보기</Link>
        </div>
      </div>
    </div>
  )
}
