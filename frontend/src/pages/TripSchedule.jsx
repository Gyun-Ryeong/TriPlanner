import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { getMyTrips, getTrip } from '../api/trips.js'
import { getNaverMapClientId } from '../api/config.js'
import { loadNaverMapsScript } from '../lib/naverMaps.js'
import './TripSchedule.css'

const REGION_CENTERS = {
  '서울 특별시': { lat: 37.5665, lng: 126.9780, zoom: 11 },
  '경기도 / 인천': { lat: 37.4563, lng: 126.7052, zoom: 10 },
  '강원도': { lat: 37.8228, lng: 128.1555, zoom: 9 },
  '충청도': { lat: 36.6357, lng: 127.4917, zoom: 9 },
  '전라도': { lat: 35.7175, lng: 127.1530, zoom: 9 },
  '경상도': { lat: 35.8714, lng: 128.6014, zoom: 9 },
  '제주도': { lat: 33.4996, lng: 126.5312, zoom: 10 },
}
const DEFAULT_CENTER = { lat: 36.5, lng: 127.8, zoom: 7 }

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
  const [mapError, setMapError] = useState('')
  const mapContainerRef = useRef(null)
  const mapInstanceRef = useRef(null)
  const markersRef = useRef([])

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

  const selectedDay = trip?.days.find((day) => day.tripDayId === selectedDayId) ?? trip?.days[0]

  useEffect(() => {
    if (!trip) return
    let cancelled = false

    getNaverMapClientId()
      .then((clientId) => loadNaverMapsScript(clientId))
      .then((naver) => {
        if (cancelled || !mapContainerRef.current) return

        const regionCenter = REGION_CENTERS[trip.region] ?? DEFAULT_CENTER
        const center = new naver.maps.LatLng(regionCenter.lat, regionCenter.lng)

        if (mapInstanceRef.current) {
          mapInstanceRef.current.setCenter(center)
          mapInstanceRef.current.setZoom(regionCenter.zoom)
        } else {
          mapInstanceRef.current = new naver.maps.Map(mapContainerRef.current, {
            center,
            zoom: regionCenter.zoom,
          })
        }
      })
      .catch(() => {
        if (!cancelled) setMapError('지도를 불러오지 못했습니다.')
      })

    return () => {
      cancelled = true
    }
  }, [trip?.tripId, trip?.region])

  useEffect(() => {
    const map = mapInstanceRef.current
    if (!map || !window.naver || !selectedDay) return

    markersRef.current.forEach((marker) => marker.setMap(null))
    markersRef.current = []

    const points = selectedDay.items.filter(
      (item) => item.placeLatitude != null && item.placeLongitude != null
    )

    points.forEach((item) => {
      markersRef.current.push(
        new window.naver.maps.Marker({
          position: new window.naver.maps.LatLng(item.placeLatitude, item.placeLongitude),
          map,
          title: item.placeName ?? '',
        })
      )
    })

    if (points.length > 0) {
      const bounds = new window.naver.maps.LatLngBounds()
      points.forEach((item) => bounds.extend(new window.naver.maps.LatLng(item.placeLatitude, item.placeLongitude)))
      map.fitBounds(bounds)
    }
  }, [selectedDay])

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
          <div className="trip-schedule__actions-row">
            <button type="button" className="btn" disabled title="준비 중인 기능입니다">일정 수정</button>
            <button type="button" className="btn btn-primary" disabled title="준비 중인 기능입니다">길찾기 시작</button>
          </div>
          <p className="trip-schedule__actions-note">일정 수정 · 길찾기 기능은 구현 중입니다.</p>
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
          {mapError ? (
            <div className="trip-schedule__map-placeholder">
              <p>{mapError}</p>
            </div>
          ) : (
            <div ref={mapContainerRef} className="trip-schedule__map-canvas" />
          )}
        </div>
      </div>
    </div>
  )
}
