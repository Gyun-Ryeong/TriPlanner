import { Fragment, useEffect, useState } from 'react'
import { getRegionAirQuality, getRegionWeather, getWeatherWarnings } from '../api/weather.js'
import { TripAlertsOverview } from '../components/TripAlertList.jsx'
import { useTripAlerts } from '../lib/tripAlertsContext.js'
import './Alerts.css'

const GRADE_CLASS = {
  좋음: 'alerts__grade--good',
  보통: 'alerts__grade--normal',
  나쁨: 'alerts__grade--bad',
  매우나쁨: 'alerts__grade--worst',
}

function formatMeasuredAt(value) {
  const m = /^(\d{4})-(\d{2})-(\d{2}) (\d{2}):\d{2}$/.exec(value ?? '')
  if (!m) return ''
  return `${Number(m[2])}월 ${Number(m[3])}일 ${m[4]}시 기준`
}

function AirCell({ metric, unit = '' }) {
  if (metric?.value == null) return <span className="alerts__meta">-</span>
  return (
    <span className="alerts__air-cell">
      <span className={`alerts__grade ${GRADE_CLASS[metric.grade] ?? ''}`}>{metric.grade}</span>
      <span className="alerts__air-value">
        {metric.value}
        {unit}
      </span>
      {metric.area && <span className="alerts__air-area">{metric.area}</span>}
    </span>
  )
}

// 강수 상태로 취급하는 하늘 상태 / 강수확률이 이 값 이상이면 눈에 띄게 알려준다 (여행 알림의 참고 기준과 같다)
const RAIN_STATUSES = ['비', '비/눈', '눈', '소나기']
const RAIN_NOTICE_POP = 50

function mostCommon(values) {
  const counts = new Map()
  values.forEach((v) => counts.set(v, (counts.get(v) ?? 0) + 1))
  let best = null
  counts.forEach((count, value) => {
    if (best === null || count > counts.get(best)) best = value
  })
  return best
}

// 권역 카드 요약: 기온 범위 + 가장 주의할 도시 한 줄
function summarizeRegion(cities) {
  const temps = cities.map((c) => c.temperature).filter((t) => t != null)
  const tempText =
    temps.length === 0
      ? '-'
      : Math.min(...temps) === Math.max(...temps)
        ? `${temps[0]}°`
        : `${Math.min(...temps)}~${Math.max(...temps)}°`

  const multi = cities.length > 1
  const byPopDesc = (a, b) => (b.precipitationProbability ?? -1) - (a.precipitationProbability ?? -1)
  const wet = cities.filter((c) => RAIN_STATUSES.includes(c.skyStatus)).sort(byPopDesc)
  const risky = cities
    .filter((c) => (c.precipitationProbability ?? 0) >= RAIN_NOTICE_POP)
    .sort(byPopDesc)

  let notice = null
  if (wet.length > 0) {
    const c = wet[0]
    const pop = c.precipitationProbability != null ? ` · 강수확률 ${c.precipitationProbability}%` : ''
    notice = `${multi ? `${c.cityName} ` : ''}${c.skyStatus}${pop}`
  } else if (risky.length > 0) {
    const c = risky[0]
    notice = `${multi ? `${c.cityName} ` : ''}강수확률 ${c.precipitationProbability}%`
  }

  return {
    tempText,
    sky: mostCommon(cities.map((c) => c.skyStatus)) ?? '-',
    notice,
  }
}

function RegionWeatherCard({ region, open, onToggle }) {
  const { tempText, sky, notice } = summarizeRegion(region.cities)
  const expandable = region.cities.length > 1

  return (
    <div className={`card alerts__weather-card ${open ? 'alerts__weather-card--open' : ''}`}>
      <div className="alerts__weather-top">
        <span>{region.regionName}</span>
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
      .catch(() => {
        if (!cancelled) setAirError('대기질 정보를 불러오지 못했습니다.')
      })
      .finally(() => {
        if (!cancelled) setAirLoading(false)
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
          <p className="alerts__subtitle">기상청 단기예보 기반 권역별(도 단위) 날씨와 기상특보, 에어코리아 대기질을 확인하세요.</p>
        </div>
      </div>

      <div className="card alerts__signals alerts__trips">
        <div className="alerts__signals-head">
          <p className="card-label">내 여행 알림 (여행 3일 전부터)</p>
        </div>
        <TripAlertsOverview data={tripAlerts.data} loading={tripAlerts.loading} error={tripAlerts.error} />
      </div>

      {loading && <p className="alerts__meta">불러오는 중...</p>}
      {error && <p className="alerts__meta">{error}</p>}

      {!loading && !error && (
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
                open={openWeather.has(w.regionId)}
                onToggle={() => toggleIn(setOpenWeather, w.regionId)}
              />
            ))}
          </div>
        </>
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
      </div>

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
  )
}
