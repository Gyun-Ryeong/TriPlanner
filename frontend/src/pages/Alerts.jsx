import { useEffect, useState } from 'react'
import { getRegionWeather } from '../api/weather.js'
import './Alerts.css'

export default function Alerts() {
  const [weather, setWeather] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false

    getRegionWeather()
      .then((data) => {
        if (!cancelled) setWeather(data)
      })
      .catch(() => {
        if (!cancelled) setError('날씨 정보를 불러오지 못했습니다.')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [])

  return (
    <div className="alerts">
      <div className="alerts__header">
        <div>
          <p className="alerts__eyebrow">LIVE TRAVEL SIGNAL</p>
          <h1 className="alerts__title">실시간 여행 알림</h1>
          <p className="alerts__subtitle">기상청 단기예보 기반 권역별 날씨를 확인하세요.</p>
        </div>
      </div>

      {loading && <p className="alerts__meta">불러오는 중...</p>}
      {error && <p className="alerts__meta">{error}</p>}

      {!loading && !error && (
        <div className="alerts__weather-grid">
          {weather.map((w) => (
            <div key={w.regionId} className="card alerts__weather-card">
              <div className="alerts__weather-top">
                <span>{w.regionName}</span>
              </div>
              <p className="alerts__temp">{w.temperature != null ? `${w.temperature}°` : '-'}</p>
              <p className="alerts__meta">{w.skyStatus}</p>
              <p className="alerts__rain">강수확률 {w.precipitationProbability != null ? `${w.precipitationProbability}%` : '-'}</p>
            </div>
          ))}
        </div>
      )}

      <div className="card alerts__signals-placeholder">
        <p className="card-label">위험·안전 신호</p>
        <p className="alerts__placeholder-text">에어코리아·기상특보 연동은 구현 중입니다.</p>
      </div>
    </div>
  )
}
