import { Link } from 'react-router-dom'
import { ALERT_LEVEL_LABEL } from '../lib/tripAlertsContext.js'
import './TripAlertList.css'

export const FORECAST_NOTICE =
  '본 서비스의 예보는 여행일 기준 3일 이내에서만 제공됩니다. 그 외 기간의 구체적인 예보는 기상청 등 공식 사이트에서 확인해 주세요.'

function formatDday(daysUntilStart) {
  if (daysUntilStart < 0) return '여행 중'
  if (daysUntilStart === 0) return '오늘 출발'
  return `D-${daysUntilStart}`
}

// 강한 단계(DANGER)는 '주의', 약한 단계(CAUTION)는 '참고'로 보여준다
function isStrong(alert) {
  return alert.level === 'DANGER'
}

// 프로필에서 여행 알림을 꺼둔 상태의 안내
export function TripAlertsOff() {
  return (
    <p className="trip-alert__note">
      여행 알림이 꺼져 있어요. <Link to="/mytrips/edit">프로필 수정</Link>에서 다시 켤 수 있어요.
    </p>
  )
}

// 한 여행의 알림 (제목을 보여줄지 선택)
export function TripAlertBlock({ trip, showTitle = false }) {
  return (
    <div className="trip-alert">
      {showTitle && (
        <p className="trip-alert__title">
          <Link to={`/schedule/${trip.tripId}`}>{trip.title}</Link>
          <span className="trip-alert__meta">
            {trip.region} · {formatDday(trip.daysUntilStart)}
          </span>
        </p>
      )}

      {!trip.forecastAvailable ? (
        <p className="trip-alert__note">여행 3일 전부터 날씨·대기질 알림을 확인할 수 있어요.</p>
      ) : trip.alerts.length === 0 ? (
        <p className="trip-alert__clear">예보 기준으로 특별한 주의 사항이 없어요.</p>
      ) : (
        <ul className="trip-alert__list">
          {trip.alerts.map((alert, index) => (
            <li
              key={`${alert.kind}-${alert.date ?? 'now'}-${index}`}
              className={`trip-alert__item ${isStrong(alert) ? 'trip-alert__item--strong' : 'trip-alert__item--light'}`}
            >
              <span className={`badge ${isStrong(alert) ? 'badge-warn' : 'badge-info'}`}>
                {ALERT_LEVEL_LABEL[alert.level] ?? alert.level}
              </span>
              <span className="trip-alert__message">{alert.message}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

// Home의 '다가오는 여행' 카드용 한 줄 요약
export function TripAlertSummary({ trip }) {
  if (!trip.forecastAvailable) {
    return <p className="trip-alert__note">{formatDday(trip.daysUntilStart)} · 여행 3일 전부터 날씨·대기질 알림을 확인할 수 있어요.</p>
  }
  const strong = trip.alerts.filter(isStrong).length
  const light = trip.alerts.length - strong
  if (trip.alerts.length === 0) {
    return <p className="trip-alert__clear">예보 기준으로 특별한 주의 사항이 없어요.</p>
  }
  return (
    <p className="trip-alert__summary">
      {strong > 0 && <span className="badge badge-warn">{ALERT_LEVEL_LABEL.DANGER} {strong}건</span>}
      {light > 0 && <span className="badge badge-info">{ALERT_LEVEL_LABEL.CAUTION} {light}건</span>}
      <span className="trip-alert__meta">아래 &lsquo;실시간 여행 알림&rsquo;에서 자세히 확인하세요.</span>
    </p>
  )
}

// 모든 여행의 알림 목록 (Home 패널, 알림 탭, 헤더 종 드롭다운에서 공용)
export function TripAlertsOverview({ data, loading, error }) {
  if (!data) {
    if (loading) return <p className="trip-alert__note">불러오는 중...</p>
    if (error) return <p className="trip-alert__note">여행 알림을 불러오지 못했어요.</p>
    return null
  }

  if (!data.alertsEnabled) {
    return <TripAlertsOff />
  }

  return (
    <div className="trip-alert-overview">
      {data.trips.length === 0 ? (
        <p className="trip-alert__note">
          진행 중이거나 예정된 여행이 없어요. <Link to="/trips/new">새 여행을 만들어보세요</Link>
        </p>
      ) : (
        data.trips.map((trip) => <TripAlertBlock key={trip.tripId} trip={trip} showTitle />)
      )}

      {data.unavailableSources.length > 0 && (
        <p className="trip-alert__note">
          일부 정보({data.unavailableSources.join(', ')})를 불러오지 못해 알림에 반영되지 않았을 수 있어요. 잠시 뒤 다시 확인해 주세요.
        </p>
      )}
      {error && <p className="trip-alert__note">최신 정보를 갱신하지 못했어요. 마지막으로 불러온 내용을 보여드려요.</p>}
      <p className="trip-alert__footnote">{FORECAST_NOTICE}</p>
    </div>
  )
}
