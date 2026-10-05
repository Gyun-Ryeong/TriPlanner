import { useEffect, useState } from 'react'
import { getRegionWeather, getWeatherWarnings } from '../api/weather.js'
import './Alerts.css'

function formatAnnouncedAt(value) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return `${date.getMonth() + 1}월 ${date.getDate()}일 ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')} 발표`
}

export default function Alerts() {
  const [weather, setWeather] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const [warnings, setWarnings] = useState(null)
  const [warningsLoading, setWarningsLoading] = useState(true)
  const [warningsError, setWarningsError] = useState('')

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

    getWeatherWarnings()
      .then((data) => {
        if (!cancelled) setWarnings(data)
      })
      .catch(() => {
        if (!cancelled) setWarningsError('기상특보를 불러오지 못했습니다.')
      })
      .finally(() => {
        if (!cancelled) setWarningsLoading(false)
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
          <p className="alerts__subtitle">기상청 단기예보 기반 권역별 날씨와 기상특보를 확인하세요.</p>
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
              <p className="alerts__rain">강수확률 (다음 1시간 기준) {w.precipitationProbability != null ? `${w.precipitationProbability}%` : '-'}</p>
            </div>
          ))}
        </div>
      )}

      <div className="card alerts__signals">
        <div className="alerts__signals-head">
          <p className="card-label">기상특보 (현재 발효 중)</p>
          {warnings?.announcedAt && (
            <span className="alerts__meta">{formatAnnouncedAt(warnings.announcedAt)}</span>
          )}
        </div>

        {warningsLoading && <p className="alerts__meta">불러오는 중...</p>}
        {warningsError && <p className="alerts__meta">{warningsError}</p>}

        {!warningsLoading && !warningsError && warnings.warnings.length === 0 && (
          <p className="alerts__placeholder-text">현재 발효 중인 기상특보가 없습니다.</p>
        )}

        {!warningsLoading && !warningsError && warnings.warnings.length > 0 && (
          <ul className="alerts__warning-list">
            {warnings.warnings.map((w) => (
              <li key={w.type} className="alerts__warning">
                <span className={w.type.includes('경보') ? 'badge badge-danger' : 'badge badge-warn'}>{w.type}</span>
                <span className="alerts__warning-areas">{w.areas}</span>
              </li>
            ))}
          </ul>
        )}

        <p className="alerts__signals-note">대기오염(에어코리아) 정보는 구현 중입니다.</p>
      </div>
    </div>
  )
}
