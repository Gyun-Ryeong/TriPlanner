import './TripStats.css'

const VISITED_PLACES = [
  { name: '경주 첨성대', date: '2026.10.12 - 10.14', desc: '첨성대 핑크뮬리와 경주 황리단길 아기자기한 골목길 구경' },
  { name: '부산 해운대', date: '2026.08.20 - 08.22', desc: '여름 해운대 해변열차를 타고 푸른 바다를 보며 힐링' },
  { name: '전주 한옥마을', date: '2026.05.05 - 05.06', desc: '고즈넉한 한옥 한복 체험과 맛있는 전주 비빔밥' },
  { name: '제주 성산일출봉', date: '2026.04.10 - 04.13', desc: '성산일출봉 정상에서 맞이한 장엄한 봄 아침의 일출' },
  { name: '강릉 경포대', date: '2025.12.24 - 12.25', desc: '새해 맞이 시원하고 파란 겨울 바다 투어와 활어회' },
  { name: '여수 오동도', date: '2025.10.03 - 10.05', desc: '붉은 동백꽃길 산책과 황홀했던 여수 밤바다 야경' },
  { name: '속초 설악산', date: '2025.06.15 - 06.16', desc: '설악산 케이블카 타고 올라간 바위 절벽과 시원한 계곡' },
  { name: '담양 죽녹원', date: '2025.03.01 - 03.02', desc: '바람에 흔들리는 울창한 대나무 숲길 속 사색의 시간' },
]

export default function TripStats() {
  return (
    <div className="trip-stats">
      <h1 className="trip-stats__title">여행 통계</h1>
      <p className="trip-stats__subtitle">이민지님의 국내 여행 기록</p>

      <div className="trip-stats__summary">
        <div className="card">
          <p className="card-label">총 여행 횟수</p>
          <p className="trip-stats__summary-main">8<span>회</span></p>
        </div>
        <div className="card">
          <p className="card-label">방문한 지역</p>
          <p className="trip-stats__summary-main">5<span>곳</span></p>
        </div>
        <div className="card">
          <p className="card-label">누적 여행 일수</p>
          <p className="trip-stats__summary-main">32<span>일</span></p>
        </div>
      </div>

      <h2 className="trip-stats__section-title">방문한 여행지</h2>
      <div className="trip-stats__grid">
        {VISITED_PLACES.map((p) => (
          <div key={p.name} className="trip-stats__place card">
            <div className="trip-stats__photo" aria-hidden="true" />
            <div className="trip-stats__place-body">
              <div className="trip-stats__place-header">
                <p className="trip-stats__place-name">{p.name}</p>
                <span className="trip-stats__place-date">{p.date}</span>
              </div>
              <p className="trip-stats__place-desc">{p.desc}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
