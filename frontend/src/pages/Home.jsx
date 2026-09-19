import { Link } from 'react-router-dom'
import './Home.css'

const UPCOMING_TRIP = {
  place: '경주, 경상북도',
  date: '2026. 10. 12 — 10. 14 · D-28',
}

export default function Home() {
  return (
    <div className="home">
      <div className="home__hero">
        <div>
          <p className="home__hero-greeting">안녕하세요, 민지님</p>
          <h1 className="home__hero-title">오늘도 설레는 여행을 준비해요</h1>
        </div>
        <Link to="/trips/new" className="btn btn-primary">+ 새 여행 생성하기</Link>
      </div>

      <div className="home__stats">
        <div className="card">
          <p className="card-label">다가오는 여행</p>
          <p className="home__stat-main">{UPCOMING_TRIP.place}</p>
          <p className="home__stat-sub">{UPCOMING_TRIP.date}</p>
        </div>

        <div className="card">
          <p className="card-label">여행 안전 지수</p>
          <p className="home__stat-main home__stat-main--safe">
            92 <span className="home__stat-unit">안전</span>
          </p>
          <p className="home__stat-sub">현재 특별한 위험 요소가 없어요.</p>
        </div>

        <div className="card">
          <p className="card-label">체크리스트</p>
          <p className="home__stat-main home__stat-main--accent">7 / 10</p>
          <p className="home__stat-sub">출발 전 3개 항목을 확인하세요.</p>
        </div>
      </div>

      <div className="home__panels">
        <div className="card">
          <h3 className="home__panel-title">AI 기반 여행 챗봇</h3>
          <p className="home__panel-desc">
            최신 여행 데이터에 기반해 실시간으로 경주 맛집 및 동선을 답변해드려요.
          </p>
          <Link to="/chatbot" className="btn btn-block">챗봇 시작하기</Link>
        </div>

        <div className="card">
          <h3 className="home__panel-title">실시간 여행 알림</h3>
          <p className="home__alert-item">경주 지역은 오늘 맑음 · 가을 단풍 시즌</p>
          <Link to="/alerts" className="btn btn-block">알림 전체 보기</Link>
        </div>
      </div>
    </div>
  )
}
