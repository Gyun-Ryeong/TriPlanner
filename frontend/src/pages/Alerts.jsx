import './Alerts.css'

const WEATHER = [
  { city: '경주', status: 'safe', statusLabel: '안전', temp: 19, feel: '체감온도 쾌적', rain: 20 },
  { city: '부산', status: 'warn', statusLabel: '주의', temp: 21, feel: '오후 강한 비', rain: 80 },
  { city: '제주', status: 'danger', statusLabel: '경계', temp: 23, feel: '체감온도 쾌적', rain: 60 },
  { city: '서울', status: 'safe', statusLabel: '안전', temp: 17, feel: '체감온도 쾌적', rain: 10 },
]

const SIGNALS = [
  {
    level: 'danger',
    label: '위험',
    title: '제주 강풍주의보',
    desc: '제주 산지와 해안에 순간풍속 20m/s 이상의 강풍이 예상됩니다.',
    meta: '14:10 업데이트 · 오늘 18:00까지',
  },
  {
    level: 'warn',
    label: '주의',
    title: '부산 집중호우 가능성',
    desc: '16시부터 시간당 20~30mm의 강한 비가 내릴 수 있습니다.',
    meta: '13:45 업데이트 · 오늘 22:00까지',
  },
  {
    level: 'safe',
    label: '안전',
    title: '경주 여행 안전',
    desc: '현재 특보가 없습니다. 야외 활동하기 좋은 상태입니다.',
    meta: '13:30 업데이트',
  },
]

const RAIN_CHART = [
  { hour: '14시', pct: 20 },
  { hour: '16시', pct: 60 },
  { hour: '18시', pct: 80 },
  { hour: '20시', pct: 70 },
  { hour: '22시', pct: 30 },
]

export default function Alerts() {
  return (
    <div className="alerts">
      <div className="alerts__header">
        <div>
          <p className="alerts__eyebrow">LIVE TRAVEL SIGNAL</p>
          <h1 className="alerts__title">실시간 여행 알림</h1>
          <p className="alerts__subtitle">여행지의 날씨와 위험 신호를 한눈에 확인하세요.</p>
        </div>
        <span className="badge badge-safe">방금 업데이트 · 14:20</span>
      </div>

      <div className="alerts__weather-grid">
        {WEATHER.map((w) => (
          <div key={w.city} className="card alerts__weather-card">
            <div className="alerts__weather-top">
              <span>{w.city}</span>
              <span className={`badge badge-${w.status}`}>{w.statusLabel}</span>
            </div>
            <p className="alerts__temp">{w.temp}°</p>
            <p className="alerts__meta">{w.feel}</p>
            <p className="alerts__rain">강수 {w.rain}%</p>
          </div>
        ))}
      </div>

      <div className="alerts__body">
        <div className="card">
          <div className="alerts__section-header">
            <h2>주요 위험·안전 신호</h2>
            <span className="alerts__meta">{SIGNALS.length}개 알림</span>
          </div>

          {SIGNALS.map((s) => (
            <div key={s.title} className={`alerts__signal alerts__signal--${s.level}`}>
              <div>
                <p className="alerts__signal-title">
                  {s.title} <span className={`badge badge-${s.level}`}>{s.label}</span>
                </p>
                <p className="alerts__signal-desc">{s.desc}</p>
                <p className="alerts__meta">{s.meta}</p>
              </div>
            </div>
          ))}
        </div>

        <div className="card">
          <h2>시간대별 강수</h2>
          <p className="alerts__meta">부산 · 오늘</p>

          <div className="alerts__chart">
            {RAIN_CHART.map((d) => (
              <div key={d.hour} className="alerts__bar-col">
                <span className="alerts__bar-pct">{d.pct}%</span>
                <div className="alerts__bar" style={{ height: `${d.pct}%` }} />
                <span className="alerts__bar-hour">{d.hour}</span>
              </div>
            ))}
          </div>

          <p className="alerts__chart-tip">☂ 16시 이후 우산을 준비하고 침수 우려 지역은 피하세요.</p>
        </div>
      </div>
    </div>
  )
}
