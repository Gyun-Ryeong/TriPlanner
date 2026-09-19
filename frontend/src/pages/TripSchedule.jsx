import './TripSchedule.css'

const STOPS = [
  { order: 1, label: '현재 위치', name: '경주역', time: '09:30 출발' },
  { order: 2, label: '첫 번째 방문', name: '대릉원', time: '10:00 · 1시간 20분' },
  { order: 3, label: '점심 식사', name: '황리단길', time: '12:00 · 도보 8분' },
  { order: 4, label: '오후 일정', name: '동궁과 월지', time: '15:30 · 버스 18분' },
]

export default function TripSchedule() {
  return (
    <div className="trip-schedule">
      <div className="trip-schedule__header">
        <div>
          <p className="trip-schedule__eyebrow">다가오는 여행</p>
          <h1 className="trip-schedule__title">경주, 경상북도</h1>
          <p className="trip-schedule__meta">2026. 10. 12 – 10. 14 · 2박 3일</p>
        </div>
        <div className="trip-schedule__actions">
          <button type="button" className="btn">일정 수정</button>
          <button type="button" className="btn btn-primary">길찾기 시작</button>
        </div>
      </div>

      <div className="trip-schedule__body">
        <div className="card trip-schedule__list">
          <div className="trip-schedule__list-header">
            <div>
              <h2>1일차 동선</h2>
              <p className="trip-schedule__meta">총 8.4km · 예상 이동 1시간 12분</p>
            </div>
            <span className="badge badge-safe">4개 장소</span>
          </div>

          {STOPS.map((stop) => (
            <div key={stop.order} className="trip-schedule__stop">
              <span className="trip-schedule__stop-index">{stop.order}</span>
              <div>
                <p className="trip-schedule__stop-label">{stop.label}</p>
                <p className="trip-schedule__stop-name">{stop.name}</p>
                <p className="trip-schedule__meta">{stop.time}</p>
              </div>
            </div>
          ))}
        </div>

        <div className="card trip-schedule__map">
          <div className="trip-schedule__map-placeholder">
            <p>지도 영역</p>
            <p className="trip-schedule__map-note">카카오맵 연동 예정 (현재는 정적 화면)</p>
          </div>
        </div>
      </div>
    </div>
  )
}
