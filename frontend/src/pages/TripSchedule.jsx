import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { getMyTrips, getTrip } from '../api/trips.js'
import './TripSchedule.css'

function formatDateRange(startDate, endDate) {
  const start = new Date(startDate)
  const end = new Date(endDate)
  const nights = Math.round((end - start) / (1000 * 60 * 60 * 24))
  const startLabel = `${start.getFullYear()}. ${start.getMonth() + 1}. ${start.getDate()}`
  const endLabel = `${end.getMonth() + 1}. ${end.getDate()}`
  return `${startLabel} – ${endLabel} · ${nights}박 ${nights + 1}일`
}

function formatTime(time) {
  return time ? time.slice(0, 5) : ''
}

export default function TripSchedule() {
  const { tripId } = useParams()
  const [trip, setTrip] = useState(null)
  const [selectedDayId, setSelectedDayId] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false

    async function load() {
      setLoading(true)
      setError('')

      try {
        let targetTripId = tripId
        if (!targetTripId) {
          const trips = await getMyTrips()
          if (trips.length === 0) {
            if (!cancelled) setTrip(null)
            return
          }
          targetTripId = trips[0].tripId
        }

        const detail = await getTrip(targetTripId)
        if (!cancelled) {
          setTrip(detail)
          setSelectedDayId(detail.days[0]?.tripDayId ?? null)
        }
      } catch (err) {
        if (!cancelled) setError(err.message ?? '여행 일정을 불러오지 못했습니다.')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    load()
    return () => {
      cancelled = true
    }
  }, [tripId])

  if (loading) {
    return (
      <div className="trip-schedule">
        <p className="trip-schedule__meta">불러오는 중...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="trip-schedule">
        <p className="trip-schedule__meta">{error}</p>
      </div>
    )
  }

  if (!trip) {
    return (
      <div className="trip-schedule">
        <p className="trip-schedule__meta">아직 등록된 여행이 없어요.</p>
        <Link to="/trips/new" className="btn btn-primary">새 여행 생성하기</Link>
      </div>
    )
  }

  const selectedDay = trip.days.find((day) => day.tripDayId === selectedDayId) ?? trip.days[0]

  return (
    <div className="trip-schedule">
      <div className="trip-schedule__header">
        <div>
          <p className="trip-schedule__eyebrow">다가오는 여행</p>
          <h1 className="trip-schedule__title">{trip.title}</h1>
          <p className="trip-schedule__meta">
            {trip.region} · {formatDateRange(trip.startDate, trip.endDate)}
          </p>
        </div>
        <div className="trip-schedule__actions">
          <button type="button" className="btn">일정 수정</button>
          <button type="button" className="btn btn-primary">길찾기 시작</button>
        </div>
      </div>

      <div className="trip-schedule__body">
        <div className="card trip-schedule__list">
          <div className="trip-schedule__list-header">
            <div>
              <h2>{selectedDay?.dayNumber}일차 동선</h2>
            </div>
            <span className="badge badge-safe">{selectedDay?.items.length ?? 0}개 장소</span>
          </div>

          {trip.days.length > 1 && (
            <div className="trip-schedule__day-tabs">
              {trip.days.map((day) => (
                <button
                  key={day.tripDayId}
                  type="button"
                  className={`trip-schedule__day-tab ${day.tripDayId === selectedDay?.tripDayId ? 'trip-schedule__day-tab--active' : ''}`}
                  onClick={() => setSelectedDayId(day.tripDayId)}
                >
                  {day.dayNumber}일차
                </button>
              ))}
            </div>
          )}

          {selectedDay?.items.length === 0 && (
            <p className="trip-schedule__meta">아직 등록된 일정이 없습니다.</p>
          )}

          {selectedDay?.items.map((item) => (
            <div key={item.tripItemId} className="trip-schedule__stop">
              <span className="trip-schedule__stop-index">{item.visitOrder}</span>
              <div>
                <p className="trip-schedule__stop-label">{item.itemType}</p>
                <p className="trip-schedule__stop-name">{item.placeName ?? item.memo ?? '이름 미정'}</p>
                {item.startTime && <p className="trip-schedule__meta">{formatTime(item.startTime)}</p>}
              </div>
            </div>
          ))}
        </div>

        <div className="card trip-schedule__map">
          <div className="trip-schedule__map-placeholder">
            <p>지도 영역</p>
            <p className="trip-schedule__map-note">네이버맵 연동 예정 (현재는 정적 화면)</p>
          </div>
        </div>
      </div>
    </div>
  )
}
