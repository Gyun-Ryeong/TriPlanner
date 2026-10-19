import { useState } from 'react'
import { Link } from 'react-router-dom'
import AirCell from './AirCell.jsx'
import { summarizeRegion } from '../lib/weatherSummary.js'
import './MyRegionCard.css'

function ddayLabel(daysUntilStart) {
  if (daysUntilStart < 0) return '여행 중'
  if (daysUntilStart === 0) return '오늘 출발'
  return `D-${daysUntilStart}`
}

// 내가 여행 가는 곳 하나의 날씨·대기질·기상특보를 날씨 카드와 같은 크기의 작은 카드에 모아 보여준다 (실시간 알림 탭의 맨 위)
// region: { regionName, city, trips: [{ tripId, title, daysUntilStart }] } — city 가 있으면 그 도시 하나의 날씨만, 없으면 권역 요약 + 도시별 보기
// weather: 그 권역의 날씨, air: 그 권역의 대기질, warnings: 이 권역에 해당하는 발효 중 특보 목록,
// airMessage / warningsMessage: 아직 못 불러왔을 때 대신 보여줄 안내 (불러오는 중, 실패 이유)
export default function MyRegionCard({ region, weather, air, airMessage, warnings, warningsMessage }) {
  const [open, setOpen] = useState(false)
  const cities = region.city ? weather.cities.filter((c) => c.cityName === region.city) : weather.cities
  const { tempText, sky, notice } = summarizeRegion(cities)
  const expandable = !region.city && weather.cities.length > 1

  return (
    <section className="card alerts__weather-card my-region" aria-label={`${region.city ?? region.regionName} 여행지 현황`}>
      <ul className="my-region__trips">
        {region.trips.map((trip) => (
          <li key={trip.tripId}>
            <Link to={`/schedule/${trip.tripId}`} className="my-region__trip-title">{trip.title}</Link>
            <span className="my-region__dday">{ddayLabel(trip.daysUntilStart)}</span>
          </li>
        ))}
      </ul>
      <p className="my-region__place">{region.city ? `${region.regionName} · ${region.city}` : region.regionName}</p>

      <p className="alerts__temp">{tempText}</p>
      <p className="alerts__meta">{sky}</p>
      {notice ? <p className="alerts__notice">{notice}</p> : <p className="alerts__rain">강수 걱정 없어요</p>}

      {expandable && (
        <button type="button" className="alerts__expand-btn" aria-expanded={open} onClick={() => setOpen((prev) => !prev)}>
          도시별 보기 ({weather.cities.length})
          <span className={`alerts__chevron ${open ? 'alerts__chevron--open' : ''}`} aria-hidden="true">▾</span>
        </button>
      )}
      {expandable && open && (
        <ul className="alerts__city-list">
          {weather.cities.map((c) => (
            <li key={c.cityName} className="alerts__city">
              <span className="alerts__city-name">{c.cityName}</span>
              <span className="alerts__city-sky">{c.skyStatus}</span>
              <span className="alerts__city-temp">{c.temperature != null ? `${c.temperature}°` : '-'}</span>
              <span className="alerts__city-pop">
                {c.precipitationProbability != null ? `${c.precipitationProbability}%` : '-'}
              </span>
            </li>
          ))}
        </ul>
      )}

      <dl className="my-region__extras">
        {air ? (
          <>
            <div>
              <dt>미세먼지</dt>
              <dd><AirCell metric={air.pm10} /></dd>
            </div>
            <div>
              <dt>초미세먼지</dt>
              <dd><AirCell metric={air.pm25} /></dd>
            </div>
          </>
        ) : (
          <div>
            <dt>대기질</dt>
            <dd className="alerts__meta">{airMessage}</dd>
          </div>
        )}
        <div>
          <dt>기상특보</dt>
          <dd>
            {warnings ? (
              warnings.length === 0 ? (
                <span className="alerts__meta">없음</span>
              ) : (
                <span className="my-region__warnings">
                  {warnings.map((w) => (
                    <span key={w.type} className={`badge ${w.type.includes('경보') ? 'badge-warn' : 'badge-info'}`}>{w.type}</span>
                  ))}
                </span>
              )
            ) : (
              <span className="alerts__meta">{warningsMessage}</span>
            )}
          </dd>
        </div>
      </dl>
    </section>
  )
}
