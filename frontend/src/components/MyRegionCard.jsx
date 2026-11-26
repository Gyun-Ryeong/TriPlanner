import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import AirCell from './AirCell.jsx'
import { summarizeRegion } from '../lib/weatherSummary.js'
import './MyRegionCard.css'

function ddayLabel(daysUntilStart) {
  if (daysUntilStart < 0) return '여행 중'
  if (daysUntilStart === 0) return '오늘 출발'
  return `D-${daysUntilStart}`
}

function TripRow({ trip }) {
  return (
    <li>
      <Link to={`/schedule/${trip.tripId}`} className="my-region__trip-title" title={trip.title}>{trip.title}</Link>
      <span className="my-region__dday">{ddayLabel(trip.daysUntilStart)}</span>
    </li>
  )
}

function WarningBadge({ warning }) {
  return <span className={`badge ${warning.type.includes('경보') ? 'badge-warn' : 'badge-info'}`}>{warning.type}</span>
}

// 내가 여행 가는 곳 하나의 날씨·대기질·기상특보를 날씨 카드와 같은 크기의 작은 카드에 모아 보여준다 (실시간 알림 탭의 맨 위)
// 모든 카드가 같은 칸(여행 1개·날씨·대기질·특보 1개)만 보여 줘서 높이가 같다. 나머지 여행, 도시별 날씨, 나머지 특보는
// 카드 위에 뜨는 드롭다운에서 본다 (펼쳐도 카드 높이는 그대로)
// region: { regionName, city, trips: [{ tripId, title, daysUntilStart }] } — city 가 있으면 그 도시 하나의 날씨만, 없으면 권역 요약 + 도시별 날씨
// weather: 그 권역의 날씨, air: 그 권역의 대기질, warnings: 이 권역에 해당하는 발효 중 특보 목록,
// airMessage / warningsMessage: 아직 못 불러왔을 때 대신 보여줄 안내 (불러오는 중, 실패 이유)
export default function MyRegionCard({ region, weather, air, airMessage, warnings, warningsMessage }) {
  const [open, setOpen] = useState(false)
  const moreRef = useRef(null)
  const cities = region.city ? weather.cities.filter((c) => c.cityName === region.city) : weather.cities
  const { tempText, sky, notice } = summarizeRegion(cities)

  const [firstTrip, ...otherTrips] = region.trips
  const showCities = !region.city && weather.cities.length > 1
  // 카드에는 특보를 하나만 보여 주므로 경보를 앞에 둔다
  const sortedWarnings = [...(warnings ?? [])].sort((a, b) => b.type.includes('경보') - a.type.includes('경보'))
  const moreParts = [
    otherTrips.length > 0 && `여행 +${otherTrips.length}`,
    showCities && `도시 ${weather.cities.length}`,
    sortedWarnings.length > 1 && `특보 ${sortedWarnings.length}`,
  ].filter(Boolean)
  const hasMore = moreParts.length > 0

  // 드롭다운은 바깥을 누르거나 Esc 를 누르면 닫힌다
  useEffect(() => {
    if (!open) return undefined
    const onPointer = (event) => {
      if (!moreRef.current?.contains(event.target)) setOpen(false)
    }
    const onKey = (event) => {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onPointer)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onPointer)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  return (
    <section className="card alerts__weather-card my-region" aria-label={`${region.city ?? region.regionName} 여행지 현황`}>
      <ul className="my-region__trips">
        <TripRow trip={firstTrip} />
      </ul>
      <p className="my-region__place">{region.city ? `${region.regionName} · ${region.city}` : region.regionName}</p>

      <p className="alerts__temp">{tempText}</p>
      <p className="alerts__meta">{sky}</p>
      <p className={`my-region__line ${notice ? 'alerts__notice' : 'alerts__rain'}`} title={notice ?? undefined}>
        {notice ?? '강수 걱정 없어요'}
      </p>

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
              sortedWarnings.length === 0 ? (
                <span className="alerts__meta">없음</span>
              ) : (
                <span className="my-region__warnings">
                  <WarningBadge warning={sortedWarnings[0]} />
                  {sortedWarnings.length > 1 && <span className="alerts__meta">외 {sortedWarnings.length - 1}</span>}
                </span>
              )
            ) : (
              <span className="alerts__meta">{warningsMessage}</span>
            )}
          </dd>
        </div>
      </dl>

      {/* 더 볼 내용이 없는 카드도 같은 자리를 비워 둬서 높이를 맞춘다 */}
      <div className="my-region__more" ref={moreRef}>
        {hasMore && (
          <button type="button" className="my-region__more-btn" aria-expanded={open} onClick={() => setOpen((prev) => !prev)}>
            <span>자세히 <small>{moreParts.join(' · ')}</small></span>
            <span className={`alerts__chevron ${open ? 'alerts__chevron--open' : ''}`} aria-hidden="true">▾</span>
          </button>
        )}
        {hasMore && open && (
          <div className="my-region__dropdown">
            {otherTrips.length > 0 && (
              <div>
                <p className="my-region__drop-title">같은 곳의 다른 여행</p>
                <ul className="my-region__trips">
                  {otherTrips.map((trip) => (
                    <TripRow key={trip.tripId} trip={trip} />
                  ))}
                </ul>
              </div>
            )}
            {showCities && (
              <div>
                <p className="my-region__drop-title">도시별 날씨</p>
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
              </div>
            )}
            {sortedWarnings.length > 1 && (
              <div>
                <p className="my-region__drop-title">발효 중인 기상특보</p>
                <span className="my-region__warnings my-region__warnings--all">
                  {sortedWarnings.map((w) => (
                    <WarningBadge key={w.type} warning={w} />
                  ))}
                </span>
              </div>
            )}
          </div>
        )}
      </div>
    </section>
  )
}
