import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { getSharedTrip } from '../api/shared.js'
import { getNaverMapClientId } from '../api/config.js'
import { loadNaverMapsScript } from '../lib/naverMaps.js'
import { placeLabel } from '../lib/tripPlace.js'
import { dayLabel, durationLabel } from '../lib/tripDuration.js'
import './TripSchedule.css'
import './SharedTrip.css'

const DEFAULT_CENTER = { lat: 36.5, lng: 127.8, zoom: 7 }

function formatDateRange(startDate, endDate) {
  const start = new Date(startDate)
  const end = new Date(endDate)
  const nights = Math.round((end - start) / (1000 * 60 * 60 * 24))
  return `${start.getFullYear()}. ${start.getMonth() + 1}. ${start.getDate()} – ${end.getMonth() + 1}. ${end.getDate()} · ${durationLabel(nights)}`
}

function formatTime(time) {
  return time ? time.slice(0, 5) : ''
}

// 공유 링크(/shared/:code)로 여는 읽기 전용 일정. 로그인 없이 볼 수 있고 수정·길찾기·알림은 없다
export default function SharedTrip() {
  const { code } = useParams()
  const [trip, setTrip] = useState(null)
  const [selectedDayId, setSelectedDayId] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [mapError, setMapError] = useState('')
  const [mapReady, setMapReady] = useState(false)
  const mapContainerRef = useRef(null)
  const mapInstanceRef = useRef(null)
  const markersRef = useRef([])
  const linesRef = useRef([])

  useEffect(() => {
    let cancelled = false
    getSharedTrip(code)
      .then((data) => {
        if (cancelled) return
        setTrip(data)
        setSelectedDayId(data.days[0]?.tripDayId ?? null)
      })
      .catch((err) => {
        if (!cancelled) setError(err.message ?? '일정을 불러오지 못했어요.')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [code])

  const selectedDay = trip?.days.find((day) => day.tripDayId === selectedDayId) ?? trip?.days[0]

  // 장소만 1, 2, 3… 번호를 받는다 (메모만 있는 항목은 번호를 차지하지 않는다)
  const stopNumbers = new Map()
  selectedDay?.items.forEach((item) => {
    if (item.placeId) stopNumbers.set(item.tripItemId, stopNumbers.size + 1)
  })

  useEffect(() => {
    if (!trip) return undefined
    let cancelled = false
    getNaverMapClientId()
      .then((clientId) => loadNaverMapsScript(clientId))
      .then((naver) => {
        if (cancelled || !mapContainerRef.current) return
        if (!mapInstanceRef.current) {
          mapInstanceRef.current = new naver.maps.Map(mapContainerRef.current, {
            center: new naver.maps.LatLng(DEFAULT_CENTER.lat, DEFAULT_CENTER.lng),
            zoom: DEFAULT_CENTER.zoom,
          })
        }
        setMapReady(true)
      })
      .catch(() => {
        if (!cancelled) setMapError('지도를 불러오지 못했습니다.')
      })
    return () => {
      cancelled = true
    }
  }, [trip])

  useEffect(() => {
    const map = mapInstanceRef.current
    // 등록되지 않은 주소에서는 지도 인증이 실패해 naver.maps 가 비어 있으므로, 그때는 마커를 그리지 않는다
    if (!map || !window.naver?.maps || !selectedDay) return

    markersRef.current.forEach((marker) => marker.setMap(null))
    markersRef.current = []
    linesRef.current.forEach((line) => line.setMap(null))
    linesRef.current = []

    const points = selectedDay.items
      .map((item) => ({ item, number: stopNumbers.get(item.tripItemId) }))
      .filter(({ item }) => item.placeLatitude != null && item.placeLongitude != null)
    const path = points.map(({ item }) => new window.naver.maps.LatLng(item.placeLatitude, item.placeLongitude))

    // 같은 좌표(재방문 등)의 마커가 겹치지 않게 "1·3"처럼 번호를 합쳐 하나로 그린다
    const groups = new Map()
    points.forEach(({ item, number }, i) => {
      const key = `${item.placeLatitude},${item.placeLongitude}`
      const group = groups.get(key) ?? { position: path[i], name: item.placeName ?? '', numbers: [] }
      group.numbers.push(number)
      groups.set(key, group)
    })
    groups.forEach(({ position, name, numbers }) => {
      markersRef.current.push(
        new window.naver.maps.Marker({
          position,
          map,
          title: name,
          icon: {
            content: `<div class="trip-schedule__marker">${numbers.join('·')}</div>`,
            anchor: new window.naver.maps.Point(14, 14),
          },
        })
      )
    })

    if (path.length > 1) {
      linesRef.current.push(
        new window.naver.maps.Polyline({
          map,
          path,
          strokeColor: '#3b5bdb',
          strokeOpacity: 0.6,
          strokeWeight: 4,
          strokeStyle: 'shortdash',
          strokeLineJoin: 'round',
        })
      )
    }
    if (path.length > 0) {
      const bounds = new window.naver.maps.LatLngBounds()
      path.forEach((latLng) => bounds.extend(latLng))
      map.fitBounds(bounds)
    }
    // stopNumbers 는 selectedDay 에서 매번 새로 만들어지므로 의존성에서 뺀다
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedDay, mapReady])

  if (loading) {
    return (
      <div className="trip-schedule">
        <p className="trip-schedule__meta">불러오는 중...</p>
      </div>
    )
  }

  if (error || !trip) {
    return (
      <div className="trip-schedule">
        <div className="empty-state shared-trip__empty">
          <p className="empty-state__title">일정을 볼 수 없어요</p>
          <p className="empty-state__desc">공유가 중단되었거나 존재하지 않는 링크예요. 링크를 보낸 사람에게 다시 확인해 보세요.</p>
          <Link to="/" className="btn btn-primary">TriPlanner 홈으로</Link>
        </div>
      </div>
    )
  }

  return (
    <div className="trip-schedule">
      <div className="trip-schedule__header">
        <div>
          <p className="trip-schedule__eyebrow">
            {trip.ownerNickname ? `${trip.ownerNickname}님이 공유한 여행` : '공유된 여행'} · 보기 전용
          </p>
          <h1 className="trip-schedule__title">{trip.title}</h1>
          <p className="trip-schedule__meta">
            {placeLabel(trip)} · {formatDateRange(trip.startDate, trip.endDate)}
          </p>
        </div>
        <div className="trip-schedule__actions">
          <Link to="/trips/new" className="btn btn-primary">나도 여행 계획 만들기</Link>
        </div>
      </div>

      <div className="trip-schedule__body">
        <div className="card trip-schedule__list">
          <div className="trip-schedule__list-header">
            <div>
              <h2>{dayLabel(selectedDay?.dayNumber, trip.days.length)} 동선</h2>
            </div>
            <span className="badge badge-safe">{stopNumbers.size}개 장소</span>
          </div>

          {trip.days.length > 1 && (
            <div className="trip-schedule__day-tabs">
              <div className="trip-schedule__day-tab-list">
                {trip.days.map((day) => (
                  <button
                    key={day.tripDayId}
                    type="button"
                    className={`trip-schedule__day-tab ${day.tripDayId === selectedDay?.tripDayId ? 'trip-schedule__day-tab--active' : ''}`}
                    onClick={() => setSelectedDayId(day.tripDayId)}
                  >
                    {day.dayNumber}일차 ({day.items.filter((item) => item.placeId).length})
                  </button>
                ))}
              </div>
            </div>
          )}

          {selectedDay?.items.length === 0 && <p className="trip-schedule__meta">이 날은 아직 등록된 일정이 없어요.</p>}

          {selectedDay?.items.map((item) => (
            <div className="trip-schedule__stop" key={item.tripItemId}>
              {item.placeId ? (
                <span className="trip-schedule__stop-index">{stopNumbers.get(item.tripItemId)}</span>
              ) : (
                <span className="trip-schedule__stop-index trip-schedule__stop-index--memo" aria-label="메모">
                  ✎
                </span>
              )}
              <div className="trip-schedule__stop-body">
                <p className="trip-schedule__stop-label">{item.itemType}</p>
                <p className="trip-schedule__stop-name">{item.placeName ?? item.memo ?? '이름 미정'}</p>
                {item.startTime && <p className="trip-schedule__meta">{formatTime(item.startTime)}</p>}
                {item.placeName && item.memo && <p className="trip-schedule__meta">{item.memo}</p>}
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
