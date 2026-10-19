import { Fragment, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ApiError } from '../api/client.js'
import { getMyTrips } from '../api/trips.js'
import { getRegionAirQuality, getRegionWeather, getWeatherWarnings } from '../api/weather.js'
import AirCell from '../components/AirCell.jsx'
import { MapIcon } from '../components/Icons.jsx'
import MyRegionCard from '../components/MyRegionCard.jsx'
import { PrepAlertsSection, TripAlertsOverview } from '../components/TripAlertList.jsx'
import { useTripAlerts } from '../lib/tripAlertsContext.js'
import { myRegionsOf, summarizeRegion, upcomingTripsOf, warningsForRegion } from '../lib/weatherSummary.js'
import './Alerts.css'

function formatMeasuredAt(value) {
  const m = /^(\d{4})-(\d{2})-(\d{2}) (\d{2}):\d{2}$/.exec(value ?? '')
  if (!m) return ''
  return `${Number(m[2])}월 ${Number(m[3])}일 ${m[4]}시 기준`
}

function RegionWeatherCard({ region, open, mine, onToggle }) {
  const { tempText, sky, notice } = summarizeRegion(region.cities)
  const expandable = region.cities.length > 1

  return (
    <div className={`card alerts__weather-card ${open ? 'alerts__weather-card--open' : ''}`}>
      <div className="alerts__weather-top">
        <span>{region.regionName}</span>
        {mine && <span className="badge badge-info alerts__mine-badge">내 여행지</span>}
      </div>
      <p className="alerts__temp">{tempText}</p>
      <p className="alerts__meta">{sky}</p>
      {notice ? (
        <p className="alerts__notice">{notice}</p>
      ) : (
        <p className="alerts__rain">강수 걱정 없어요</p>
      )}

      {expandable && (
        <button
          type="button"
          className="alerts__expand-btn"
          aria-expanded={open}
          onClick={onToggle}
        >
          도시별 보기 ({region.cities.length})
          <span className={`alerts__chevron ${open ? 'alerts__chevron--open' : ''}`} aria-hidden="true">▾</span>
        </button>
      )}

      {expandable && open && (
        <ul className="alerts__city-list">
          {region.cities.map((c) => (
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
    </div>
  )
}

function formatAnnouncedAt(value) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return `${date.getMonth() + 1}월 ${date.getDate()}일 ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')} 발표`
}

export default function Alerts() {
  const tripAlerts = useTripAlerts()
  const [weather, setWeather] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const [warnings, setWarnings] = useState(null)
  const [warningsLoading, setWarningsLoading] = useState(true)
  const [warningsError, setWarningsError] = useState('')

  const [airQuality, setAirQuality] = useState([])
  const [airLoading, setAirLoading] = useState(true)
  const [airError, setAirError] = useState('')

  // 내 여행 목록 (아직 못 받았으면 null). 알림 설정과 상관없이 내 여행지 날씨를 보여주려고 따로 받는다
  const [myTrips, setMyTrips] = useState(null)
  // '전체 지역 보기'를 눌러 펼쳤는지
  const [showAll, setShowAll] = useState(false)

  // 펼쳐 둔 권역 id (날씨 카드 / 대기질 표)
  const [openWeather, setOpenWeather] = useState(() => new Set())
  const [openAir, setOpenAir] = useState(() => new Set())

  function toggleIn(setter, id) {
    setter((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  useEffect(() => {
    let cancelled = false

    getMyTrips()
      .then((trips) => {
        if (!cancelled) setMyTrips(upcomingTripsOf(trips))
      })
      .catch(() => {
        // 여행 목록을 못 받아도 전체 지역 날씨는 볼 수 있다
        if (!cancelled) setMyTrips([])
      })

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

    getRegionAirQuality()
      .then((data) => {
        if (!cancelled) setAirQuality(data)
      })
      .catch((err) => {
        // 호출 한도 초과처럼 서버가 이유를 알려준 경우에는 그 안내를 그대로 보여준다
        if (!cancelled) setAirError(err instanceof ApiError && err.message ? err.message : '대기질 정보를 불러오지 못했습니다.')
      })
      .finally(() => {
        if (!cancelled) setAirLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [])

  const myRegions = myTrips ? myRegionsOf(myTrips, weather) : []
  const myRegionIds = new Set(myRegions.map((r) => r.regionId))
  const myPartLoading = loading || myTrips === null
  // 내 여행지가 없으면 보여줄 게 없으므로 전체 지역을 처음부터 펼쳐 둔다
  const noMyRegion = !myPartLoading && !error && myRegions.length === 0
  const allVisible = showAll || noMyRegion

  const airMessage = airLoading ? '불러오는 중...' : airError || '정보 없음'
  const warningsMessage = warningsLoading ? '불러오는 중...' : warningsError || '정보 없음'

  return (
    <div className="alerts">
      <div className="page-head">
        <div>
          <p className="page-eyebrow">LIVE TRAVEL SIGNAL</p>
          <h1 className="page-title">실시간 여행 알림</h1>
          <p className="page-subtitle">내가 여행 가는 지역의 날씨·대기질·기상특보를 가장 먼저 보여드려요. 다른 지역은 아래에서 펼쳐 볼 수 있어요.</p>
        </div>
      </div>

      <div className="alerts__section-head">
        <h2 className="alerts__section-title">내 여행지 현황</h2>
        {!noMyRegion && !myPartLoading && !error && (
          <button
            type="button"
            className="btn btn-primary alerts__all-toggle"
            aria-expanded={showAll}
            aria-controls="alerts-all-regions"
            onClick={() => setShowAll((prev) => !prev)}
          >
            <MapIcon size={16} />
            {showAll ? '전체 지역 접기' : '전체 지역 날씨 보기'}
            <span className={`alerts__chevron ${showAll ? 'alerts__chevron--open' : ''}`} aria-hidden="true">▾</span>
          </button>
        )}
      </div>
      {myPartLoading && !error && <p className="alerts__meta">불러오는 중...</p>}
      {error && <p className="alerts__meta">{error}</p>}
      {!myPartLoading && !error && myRegions.length > 0 && (
        <div className="alerts__weather-grid">
          {myRegions.map((region) => (
            <MyRegionCard
              key={region.key}
              region={region}
              weather={weather.find((w) => w.regionId === region.regionId)}
              air={airQuality.find((a) => a.regionId === region.regionId)}
              airMessage={airMessage}
              warnings={warnings ? warningsForRegion(region.regionId, warnings.warnings) : null}
              warningsMessage={warningsMessage}
            />
          ))}
        </div>
      )}
      {noMyRegion && (
        <div className="card alerts__no-trip">
          {myTrips.length === 0 ? (
            <p>
              예정된 여행이 없어요. <Link to="/trips/new">새 여행을 만들면</Link> 여행지의 날씨를 가장 먼저 보여드려요.
              지금은 전체 지역을 보여드릴게요.
            </p>
          ) : (
            <p>여행 지역의 날씨 정보를 찾지 못했어요. 아래 전체 지역에서 확인해 주세요.</p>
          )}
        </div>
      )}

      {allVisible && !myPartLoading && (
        <div id="alerts-all-regions" className="alerts__all">
          {/* 현재 발효 중인 기상특보 (전국) */}
          <div className="alerts__banners">
            {warningsLoading && <p className="alerts__meta">기상특보를 불러오는 중...</p>}
            {warningsError && <p className="alerts__meta">{warningsError}</p>}

            {!warningsLoading && !warningsError && warnings.warnings.length === 0 && (
              <div className="alerts__banner alerts__banner--clear">
                <p className="alerts__banner-title">현재 발효 중인 기상특보가 없습니다</p>
              </div>
            )}

            {!warningsLoading &&
              !warningsError &&
              warnings.warnings.map((w) => (
                <div
                  key={w.type}
                  className={`alerts__banner ${w.type.includes('경보') ? 'alerts__banner--danger' : ''}`}
                >
                  <div className="alerts__banner-main">
                    <p className="alerts__banner-title">{w.type}</p>
                    <p className="alerts__banner-areas">{w.areas}</p>
                  </div>
                  {warnings.announcedAt && (
                    <span className="alerts__banner-time">{formatAnnouncedAt(warnings.announcedAt)}</span>
                  )}
                </div>
              ))}
          </div>

          {!error && (
            <>
              <p className="alerts__meta alerts__weather-hint">
                권역 안 도시들의 기온 범위와 가장 주의할 도시를 보여줘요. &apos;도시별 보기&apos;를 누르면 부산·대구 같은 도시별
                날씨를 확인할 수 있어요. (기상청 단기예보, 기온·강수확률은 다음 예보 시각 기준)
              </p>
              <div className="alerts__weather-grid">
                {weather.map((w) => (
                  <RegionWeatherCard
                    key={w.regionId}
                    region={w}
                    mine={myRegionIds.has(w.regionId)}
                    open={openWeather.has(w.regionId)}
                    onToggle={() => toggleIn(setOpenWeather, w.regionId)}
                  />
                ))}
              </div>
            </>
          )}

          <div className="card alerts__signals alerts__air">
            <div className="alerts__signals-head">
              <p className="card-label">대기질 (현재 측정)</p>
              {airQuality.length > 0 && (
                <span className="alerts__meta">{formatMeasuredAt(airQuality[0].dataTime)}</span>
              )}
            </div>

            {airLoading && <p className="alerts__meta">불러오는 중...</p>}
            {airError && <p className="alerts__meta">{airError}</p>}

            {!airLoading && !airError && airQuality.length > 0 && (
              <div className="alerts__air-scroll">
                <table className="alerts__air-table">
                  <thead>
                    <tr>
                      <th>권역</th>
                      <th>미세먼지 (PM10)</th>
                      <th>초미세먼지 (PM2.5)</th>
                      <th>오존 (ppm)</th>
                      <th>통합대기지수</th>
                    </tr>
                  </thead>
                  <tbody>
                    {airQuality.map((a) => {
                      const expandable = a.areas.length > 1
                      const open = openAir.has(a.regionId)
                      return (
                        <Fragment key={a.regionId}>
                          <tr>
                            <th scope="row">
                              {expandable ? (
                                <button
                                  type="button"
                                  className="alerts__expand-btn alerts__expand-btn--row"
                                  aria-expanded={open}
                                  onClick={() => toggleIn(setOpenAir, a.regionId)}
                                >
                                  {a.regionName}
                                  <span className={`alerts__chevron ${open ? 'alerts__chevron--open' : ''}`} aria-hidden="true">▾</span>
                                </button>
                              ) : (
                                a.regionName
                              )}
                            </th>
                            <td><AirCell metric={a.pm10} unit="㎍/㎥" /></td>
                            <td><AirCell metric={a.pm25} unit="㎍/㎥" /></td>
                            <td><AirCell metric={a.o3} /></td>
                            <td><AirCell metric={a.khai} /></td>
                          </tr>
                          {expandable && open &&
                            a.areas.map((area) => (
                              <tr key={area.areaName} className="alerts__air-subrow">
                                <th scope="row">{area.areaName}</th>
                                <td><AirCell metric={area.pm10} unit="㎍/㎥" /></td>
                                <td><AirCell metric={area.pm25} unit="㎍/㎥" /></td>
                                <td><AirCell metric={area.o3} /></td>
                                <td><AirCell metric={area.khai} /></td>
                              </tr>
                            ))}
                        </Fragment>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )}

            <p className="alerts__signals-note">
              에어코리아 실시간 측정 자료입니다. 권역 행은 소속 시도 중 가장 나쁜(높은) 값이며 시도 이름을 함께 표시하고,
              권역 이름을 누르면 시도별 값을 볼 수 있어요. 시도 값은 시도 안 측정소의 평균입니다. (측정소·시기에 따라 실제 체감과 다를 수 있습니다.)
            </p>
          </div>
        </div>
      )}

      <div className="card alerts__signals alerts__trips">
        <div className="alerts__signals-head">
          <p className="card-label">내 여행 알림 (여행 3일 전부터)</p>
        </div>
        <TripAlertsOverview data={tripAlerts.data} loading={tripAlerts.loading} error={tripAlerts.error} />
      </div>

      <div className="card alerts__signals alerts__trips">
        <div className="alerts__signals-head">
          <p className="card-label">일정 변경·준비 알림</p>
        </div>
        <PrepAlertsSection prep={tripAlerts.prep} showEmpty />
      </div>
    </div>
  )
}
