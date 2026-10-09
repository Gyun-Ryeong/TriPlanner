import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { countAlerts, hasStrongAlert, useTripAlerts } from '../lib/tripAlertsContext.js'
import { TripAlertsOff, TripAlertsOverview } from './TripAlertList.jsx'
import './AlertBell.css'

// 종 드롭다운에는 알림이 있는 여행만 보여준다 (이상 없는 여행의 안내 문구는 생략)
function alertTripsOnly(data) {
  return data ? { ...data, trips: data.trips.filter((trip) => trip.alerts.length > 0) } : data
}

export default function AlertBell() {
  const { data, loading, error } = useTripAlerts()
  const [open, setOpen] = useState(false)
  const rootRef = useRef(null)

  const count = countAlerts(data)
  const strong = hasStrongAlert(data)

  useEffect(() => {
    if (!open) return undefined

    function handlePointerDown(event) {
      if (rootRef.current && !rootRef.current.contains(event.target)) setOpen(false)
    }
    function handleKeyDown(event) {
      if (event.key === 'Escape') setOpen(false)
    }

    document.addEventListener('mousedown', handlePointerDown)
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('mousedown', handlePointerDown)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [open])

  function renderBody() {
    if (data && !data.alertsEnabled) {
      return <div className="alert-bell__empty"><TripAlertsOff /></div>
    }
    if (data && count === 0) {
      return (
        <div className="alert-bell__empty">
          <p>알림이 없어요.</p>
          {data.unavailableSources.length > 0 && <p className="alert-bell__empty-sub">일부 정보를 불러오지 못했어요.</p>}
        </div>
      )
    }
    return <TripAlertsOverview data={alertTripsOnly(data)} loading={loading} error={error} />
  }

  return (
    <div className="alert-bell" ref={rootRef}>
      <button
        type="button"
        className="alert-bell__button"
        aria-label={count > 0 ? `여행 알림 ${count}건` : '여행 알림'}
        aria-expanded={open}
        onClick={() => setOpen((prev) => !prev)}
      >
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" />
          <path d="M13.73 21a2 2 0 0 1-3.46 0" />
        </svg>
        {count > 0 && (
          <span className={`alert-bell__badge ${strong ? 'alert-bell__badge--strong' : ''}`}>{count > 9 ? '9+' : count}</span>
        )}
      </button>

      {open && (
        // 안의 링크를 눌러 다른 페이지로 이동하면 드롭다운도 닫는다
        <div className="alert-bell__panel" onClick={(event) => event.target.closest('a') && setOpen(false)}>
          <p className="alert-bell__heading">내 여행 알림</p>
          {renderBody()}
          <Link to="/alerts" className="alert-bell__more">실시간 알림 전체 보기</Link>
        </div>
      )}
    </div>
  )
}
