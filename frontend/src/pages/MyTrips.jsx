import { Link } from 'react-router-dom'
import './MyTrips.css'

export default function MyTrips() {
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
          <p className="mytrips__name">이민지</p>
          <p className="mytrips__meta">minji.lee@triplanner.com · 010-1234-5678</p>
        </div>

        <Link to="/mytrips/stats" className="card mytrips__stats-card">
          <p className="card-label">여행 통계</p>
          <p className="mytrips__stats-main">8번의 여행</p>
          <p className="mytrips__meta">방문 지역 5 · 안전 알림 12회</p>
        </Link>
      </div>

      <div className="card mytrips__risk">
        <p className="card-label">다가오는 여행 위험 관리</p>
        <div className="mytrips__risk-row">
          <div>
            <p className="mytrips__risk-title">경주, 경상북도 · 2026. 10. 12</p>
            <p className="mytrips__meta">치안 안전 · 자연재해 낮음 · 의료 접근성 좋음</p>
          </div>
          <span className="badge badge-safe">안전 지수 92</span>
        </div>
      </div>
    </div>
  )
}
