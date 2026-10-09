import { Fragment, useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { addTripItem, deleteTripItem, getDayRoute, getMyTrips, getTrip, updateTripItem } from '../api/trips.js'
import { savePlace, searchPlaces } from '../api/places.js'
import { getNaverMapClientId } from '../api/config.js'
import { loadNaverMapsScript } from '../lib/naverMaps.js'
import TripDeleteButton from '../components/TripDeleteButton.jsx'
import { TripAlertBlock } from '../components/TripAlertList.jsx'
import { useTripAlerts } from '../lib/tripAlertsContext.js'
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
const MEMO_ITEM_TYPE = '메모'
const MEMO_MAX_LENGTH = 255

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

function formatDistance(meters) {
  return meters >= 1000 ? `${(meters / 1000).toFixed(1)}km` : `${meters}m`
}

function formatDuration(seconds) {
  const totalMinutes = Math.max(1, Math.round(seconds / 60))
  const hours = Math.floor(totalMinutes / 60)
  const minutes = totalMinutes % 60
  if (hours === 0) return `${minutes}분`
  return minutes === 0 ? `${hours}시간` : `${hours}시간 ${minutes}분`
}

// mode="plan": 새 여행을 만든 직후 일차별 계획을 입력하는 전용 화면 (항상 입력 상태, 길찾기·삭제 없음)
// mode="view": 기존 일정을 보고 필요할 때만 '일정 수정'으로 고치는 화면
export default function TripSchedule({ mode = 'view' }) {
  const planning = mode === 'plan'
  const { tripId } = useParams()
  const navigate = useNavigate()
  const { data: alertData } = useTripAlerts()
  const [trip, setTrip] = useState(null)
  const [selectedDayId, setSelectedDayId] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [mapError, setMapError] = useState('')
  const [mapReady, setMapReady] = useState(false)
  const [viewEditing, setViewEditing] = useState(false)
  const editing = planning || viewEditing
  const [memoText, setMemoText] = useState('')
  const [keyword, setKeyword] = useState('')
  const [searchResults, setSearchResults] = useState(null)
  const [searching, setSearching] = useState(false)
  const [editError, setEditError] = useState('')
  const [busyId, setBusyId] = useState(null)
  const busyLock = useRef(false)
  // 항목 하나의 시간·메모를 고치는 중이면 그 항목 id 와 입력값
  const [itemEdit, setItemEdit] = useState(null)
  const [route, setRoute] = useState(null)
  const [routeLoading, setRouteLoading] = useState(false)
  const routeLock = useRef(false)
  const [routeError, setRouteError] = useState('')
  const mapContainerRef = useRef(null)
  const mapInstanceRef = useRef(null)
  const markersRef = useRef([])
  const polylineRef = useRef(null)

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

  // 길찾기 결과는 계산할 때의 날짜·항목 구성에만 유효하다 (항목을 추가/삭제하거나 날짜를 바꾸면 자동으로 무효)
  const itemsSignature = selectedDay?.items.map((item) => item.tripItemId).join(',') ?? ''
  const activeRoute =
    route && route.dayId === selectedDay?.tripDayId && route.signature === itemsSignature ? route.data : null
  const routeLegs = new Map(activeRoute?.legs.map((leg) => [leg.fromItemId, leg]))
  // 경로 계산에는 좌표가 서로 다른 장소가 2곳 이상 필요하다
  const routableCount = new Set(
    selectedDay?.items
      .filter((item) => item.placeLatitude != null)
      .map((item) => `${item.placeLatitude},${item.placeLongitude}`)
  ).size

  useEffect(() => {
    setRouteError('')
  }, [selectedDay?.tripDayId, itemsSignature])

  // 같은 장소를 하루에 여러 번 방문할 수 있어서, 장소별 추가 횟수와 각 항목의 n번째 방문을 구분해 보여준다
  const placeVisitCounts = new Map()
  const visitNumbers = new Map()
  selectedDay?.items.forEach((item) => {
    if (!item.placeContentId) return
    const count = (placeVisitCounts.get(item.placeContentId) ?? 0) + 1
    placeVisitCounts.set(item.placeContentId, count)
    visitNumbers.set(item.tripItemId, count)
  })

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
        // 마커 effect 가 지도 생성보다 먼저 실행되는 경우를 위해, 지도가 준비되면 다시 그리도록 알린다
        setMapReady(true)
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
    // 등록되지 않은 주소에서는 지도 인증이 실패해 naver.maps 가 비어 있으므로, 그때는 마커를 그리지 않는다
    if (!map || !window.naver?.maps || !selectedDay) return

    markersRef.current.forEach((marker) => marker.setMap(null))
    markersRef.current = []
    polylineRef.current?.setMap(null)
    polylineRef.current = null

    // 목록의 번호(1부터)와 지도 마커 번호가 같도록, 좌표 없는 항목을 건너뛰어도 목록 기준 번호를 쓴다
    const points = selectedDay.items
      .map((item, index) => ({ item, number: index + 1 }))
      .filter(({ item }) => item.placeLatitude != null && item.placeLongitude != null)

    const path = points.map(({ item }) => new window.naver.maps.LatLng(item.placeLatitude, item.placeLongitude))

    // 같은 좌표(재방문 등)의 마커가 겹쳐 가려지지 않도록 "1·3"처럼 번호를 합쳐 하나로 그린다
    const markerGroups = new Map()
    points.forEach(({ item, number }, i) => {
      const key = `${item.placeLatitude},${item.placeLongitude}`
      const group = markerGroups.get(key) ?? { position: path[i], name: item.placeName ?? '', numbers: [] }
      group.numbers.push(number)
      markerGroups.set(key, group)
    })

    markerGroups.forEach(({ position, name, numbers }) => {
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

    // 길찾기 결과가 있으면 실제 도로 경로를, 없으면 장소들을 잇는 점선을 그린다
    const linePath = activeRoute
      ? activeRoute.path.map(([lat, lng]) => new window.naver.maps.LatLng(lat, lng))
      : path

    if (linePath.length > 1) {
      polylineRef.current = new window.naver.maps.Polyline({
        map,
        path: linePath,
        strokeColor: '#3b5bdb',
        strokeOpacity: activeRoute ? 0.9 : 0.6,
        strokeWeight: activeRoute ? 6 : 4,
        strokeStyle: activeRoute ? 'solid' : 'shortdash',
        strokeLineJoin: 'round',
      })
    }

    if (linePath.length > 0) {
      const bounds = new window.naver.maps.LatLngBounds()
      linePath.forEach((latLng) => bounds.extend(latLng))
      map.fitBounds(bounds)
    }
  }, [selectedDay, activeRoute, mapReady])

  function updateDayItems(tripDayId, updater) {
    setTrip((prev) => ({
      ...prev,
      days: prev.days.map((day) => (day.tripDayId === tripDayId ? { ...day, items: updater(day.items) } : day)),
    }))
  }

  async function handleRoute() {
    if (activeRoute) {
      setRoute(null)
      return
    }
    if (!selectedDay || routeLock.current) return
    routeLock.current = true
    setRouteLoading(true)
    setRouteError('')
    try {
      const data = await getDayRoute(trip.tripId, selectedDay.tripDayId)
      setRoute({ dayId: selectedDay.tripDayId, signature: itemsSignature, data })
    } catch (err) {
      setRouteError(err.message ?? '경로를 불러오지 못했습니다.')
    } finally {
      routeLock.current = false
      setRouteLoading(false)
    }
  }

  async function handleSearch(event) {
    event.preventDefault()
    if (!keyword.trim()) return
    setSearching(true)
    setEditError('')
    try {
      setSearchResults(await searchPlaces(keyword.trim()))
    } catch (err) {
      setEditError(err.message ?? '장소를 검색하지 못했습니다.')
    } finally {
      setSearching(false)
    }
  }

  async function handleAdd(result) {
    // state 는 리렌더 전까지 갱신되지 않아 연속 클릭을 못 막으므로, 동기적으로 바뀌는 ref 로 잠근다
    if (!selectedDay || busyLock.current) return
    busyLock.current = true
    setBusyId(result.contentId)
    setEditError('')
    try {
      const place = await savePlace(result)
      const nextOrder = Math.max(0, ...selectedDay.items.map((item) => item.visitOrder)) + 1
      const item = await addTripItem(trip.tripId, selectedDay.tripDayId, {
        placeId: place.placeId,
        itemType: result.category,
        visitOrder: nextOrder,
      })
      updateDayItems(selectedDay.tripDayId, (items) => [...items, item])
    } catch (err) {
      setEditError(err.message ?? '일정에 추가하지 못했습니다.')
    } finally {
      busyLock.current = false
      setBusyId(null)
    }
  }

  // 장소가 정해지지 않은 계획은 장소 없이 메모만 있는 항목으로 저장한다 (지도·길찾기에는 쓰이지 않음)
  async function handleAddMemo(event) {
    event.preventDefault()
    const text = memoText.trim()
    if (!text || !selectedDay || busyLock.current) return
    busyLock.current = true
    setBusyId('memo')
    setEditError('')
    try {
      const nextOrder = Math.max(0, ...selectedDay.items.map((item) => item.visitOrder)) + 1
      const item = await addTripItem(trip.tripId, selectedDay.tripDayId, {
        itemType: MEMO_ITEM_TYPE,
        visitOrder: nextOrder,
        memo: text,
      })
      updateDayItems(selectedDay.tripDayId, (items) => [...items, item])
      setMemoText('')
    } catch (err) {
      setEditError(err.message ?? '메모를 추가하지 못했습니다.')
    } finally {
      busyLock.current = false
      setBusyId(null)
    }
  }

  async function handleDelete(item) {
    if (busyLock.current) return
    busyLock.current = true
    setBusyId(item.tripItemId)
    setEditError('')
    try {
      await deleteTripItem(trip.tripId, selectedDay.tripDayId, item.tripItemId)
      updateDayItems(selectedDay.tripDayId, (items) => items.filter((it) => it.tripItemId !== item.tripItemId))
    } catch (err) {
      setEditError(err.message ?? '일정을 삭제하지 못했습니다.')
    } finally {
      busyLock.current = false
      setBusyId(null)
    }
  }

  function itemRequest(item, changes) {
    return {
      placeId: item.placeId,
      itemType: item.itemType,
      visitOrder: item.visitOrder,
      startTime: item.startTime,
      memo: item.memo,
      ...changes,
    }
  }

  function startItemEdit(item) {
    setEditError('')
    setItemEdit({ itemId: item.tripItemId, time: formatTime(item.startTime), memo: item.memo ?? '' })
  }

  async function handleSaveItem(event, item) {
    event.preventDefault()
    if (busyLock.current) return
    // 메모 항목은 메모가 곧 이름이라 비울 수 없다
    if (!item.placeId && !itemEdit.memo.trim()) {
      setEditError('메모 항목은 내용을 비울 수 없어요. 필요 없으면 삭제해 주세요.')
      return
    }
    busyLock.current = true
    setBusyId(item.tripItemId)
    setEditError('')
    try {
      const updated = await updateTripItem(trip.tripId, selectedDay.tripDayId, item.tripItemId, itemRequest(item, {
        startTime: itemEdit.time ? `${itemEdit.time}:00` : null,
        memo: itemEdit.memo.trim() || null,
      }))
      updateDayItems(selectedDay.tripDayId, (items) =>
        items.map((it) => (it.tripItemId === item.tripItemId ? updated : it)),
      )
      setItemEdit(null)
    } catch (err) {
      setEditError(err.message ?? '일정을 수정하지 못했습니다.')
    } finally {
      busyLock.current = false
      setBusyId(null)
    }
  }

  // 위/아래 항목과 자리를 바꾸고, 하루 전체 순서를 1부터 다시 매긴다 (바뀐 항목만 저장)
  async function handleMove(index, direction) {
    const items = selectedDay.items
    const target = index + direction
    if (busyLock.current || target < 0 || target >= items.length) return
    busyLock.current = true
    setBusyId(items[index].tripItemId)
    setEditError('')
    const reordered = [...items]
    ;[reordered[index], reordered[target]] = [reordered[target], reordered[index]]
    try {
      const saved = await Promise.all(
        reordered.map((item, i) =>
          item.visitOrder === i + 1
            ? item
            : updateTripItem(trip.tripId, selectedDay.tripDayId, item.tripItemId, itemRequest(item, { visitOrder: i + 1 })),
        ),
      )
      updateDayItems(selectedDay.tripDayId, () => saved)
    } catch (err) {
      setEditError(err.message ?? '순서를 바꾸지 못했습니다.')
      // 일부만 저장됐을 수 있으므로 서버 기준으로 다시 불러온다
      getTrip(trip.tripId).then(setTrip).catch(() => {})
    } finally {
      busyLock.current = false
      setBusyId(null)
    }
  }

  const tripAlert = trip ? alertData?.trips.find((t) => t.tripId === trip.tripId) : null

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
          <p className="trip-schedule__eyebrow">{planning ? '새 여행 · 일정 만들기' : '다가오는 여행'}</p>
          <h1 className="trip-schedule__title">{planning ? `${trip.title} 일정 만들기` : trip.title}</h1>
          <p className="trip-schedule__meta">
            {trip.region} · {formatDateRange(trip.startDate, trip.endDate)}
          </p>
        </div>
        {planning ? (
          <div className="trip-schedule__actions">
            <div className="trip-schedule__actions-row">
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => navigate(`/schedule/${trip.tripId}`, { replace: true })}
              >
                작성 완료
              </button>
            </div>
            <p className="trip-schedule__actions-note">
              추가한 장소와 메모는 바로 저장돼요. 완료 후에도 일정 화면의 &lsquo;일정 수정&rsquo;으로 고칠 수 있어요.
            </p>
          </div>
        ) : (
          <div className="trip-schedule__actions">
            <div className="trip-schedule__actions-row">
              <button
                type="button"
                className="btn btn-primary"
                disabled={routeLoading || (!activeRoute && routableCount < 2)}
                title={routableCount < 2 ? '서로 다른 위치의 장소가 2곳 이상 필요합니다' : undefined}
                onClick={handleRoute}
              >
                {routeLoading ? '경로 계산 중...' : activeRoute ? '길찾기 닫기' : '길찾기 시작'}
              </button>
            </div>
            {routeError ? (
              <p className="trip-schedule__actions-note trip-schedule__search-error">{routeError}</p>
            ) : (
              <p className="trip-schedule__actions-note">길찾기는 자동차 기준으로 계산됩니다.</p>
            )}
          </div>
        )}
      </div>

      {!planning && tripAlert && tripAlert.alerts.length > 0 && (
        <div className="card trip-schedule__alerts">
          <p className="card-label">이 여행의 임박 알림</p>
          <TripAlertBlock trip={tripAlert} />
        </div>
      )}

      <div className="trip-schedule__body">
        <div className="card trip-schedule__list">
          <div className="trip-schedule__list-header">
            <div>
              <h2>{selectedDay?.dayNumber}일차 동선</h2>
            </div>
            <span className="badge badge-safe">{selectedDay?.items.length ?? 0}개 장소</span>
          </div>

          {(trip.days.length > 1 || !planning) && (
            <div className="trip-schedule__day-tabs">
              <div className="trip-schedule__day-tab-list">
                {trip.days.length > 1 &&
                  trip.days.map((day) => (
                    <button
                      key={day.tripDayId}
                      type="button"
                      className={`trip-schedule__day-tab ${day.tripDayId === selectedDay?.tripDayId ? 'trip-schedule__day-tab--active' : ''}`}
                      onClick={() => setSelectedDayId(day.tripDayId)}
                    >
                      {day.dayNumber}일차 ({day.items.length})
                    </button>
                  ))}
              </div>
              {!planning && (
                <button
                  type="button"
                  className="trip-schedule__day-tab trip-schedule__edit-toggle"
                  onClick={() => {
                    setViewEditing((prev) => !prev)
                    setItemEdit(null)
                  }}
                >
                  {viewEditing ? '수정 완료' : '일정 수정'}
                </button>
              )}
            </div>
          )}

          {editing && (
            <p className="trip-schedule__edit-guide">
              {trip.days.length > 1 ? '일차 탭을 눌러 날짜별로 ' : ''}계획을 입력하세요. 장소는 아래에서 검색해 추가하고,
              장소가 아직 정해지지 않았다면 메모로 적어둘 수 있어요. 각 항목의 ↑↓로 순서를, &lsquo;수정&rsquo;으로 시간·메모를 바꿀 수 있어요.
              다 입력했으면 &lsquo;{planning ? '작성 완료' : '수정 완료'}&rsquo;를 눌러주세요.
            </p>
          )}

          {selectedDay?.items.length === 0 && (
            <p className="trip-schedule__meta">아직 등록된 일정이 없습니다.</p>
          )}

          {activeRoute && (
            <div className="trip-schedule__route-summary">
              <div>
                <p className="trip-schedule__stop-label">총 이동</p>
                <p className="trip-schedule__route-total">
                  {formatDistance(activeRoute.totalDistanceMeters)} · {formatDuration(activeRoute.totalDurationSeconds)}
                </p>
              </div>
              <p className="trip-schedule__meta">
                택시 약 {activeRoute.taxiFare.toLocaleString()}원
                {activeRoute.tollFare > 0 && ` · 통행료 ${activeRoute.tollFare.toLocaleString()}원`}
              </p>
            </div>
          )}

          {selectedDay?.items.map((item, index) => (
            <Fragment key={item.tripItemId}>
            <div className="trip-schedule__stop">
              <span className="trip-schedule__stop-index">{index + 1}</span>
              <div className="trip-schedule__stop-body">
                <p className="trip-schedule__stop-label">{item.itemType}</p>
                <p className="trip-schedule__stop-name">
                  {item.placeName ?? item.memo ?? '이름 미정'}
                  {placeVisitCounts.get(item.placeContentId) > 1 && (
                    <span className="trip-schedule__revisit">{visitNumbers.get(item.tripItemId)}번째 방문</span>
                  )}
                </p>
                {item.startTime && <p className="trip-schedule__meta">{formatTime(item.startTime)}</p>}
                {item.placeName && item.memo && <p className="trip-schedule__meta">{item.memo}</p>}
                {editing && itemEdit?.itemId === item.tripItemId && (
                  <form className="trip-schedule__item-edit" onSubmit={(event) => handleSaveItem(event, item)}>
                    <label>
                      시간
                      <input
                        type="time"
                        value={itemEdit.time}
                        onChange={(event) => setItemEdit((prev) => ({ ...prev, time: event.target.value }))}
                      />
                    </label>
                    <label>
                      {item.placeId ? '메모' : '내용'}
                      <input
                        type="text"
                        value={itemEdit.memo}
                        maxLength={MEMO_MAX_LENGTH}
                        placeholder={item.placeId ? '예: 입장권 미리 예매' : '메모 내용'}
                        onChange={(event) => setItemEdit((prev) => ({ ...prev, memo: event.target.value }))}
                      />
                    </label>
                    <div className="trip-schedule__item-edit-actions">
                      <button type="submit" className="btn btn-primary" disabled={busyId !== null}>
                        저장
                      </button>
                      <button type="button" className="btn" disabled={busyId !== null} onClick={() => setItemEdit(null)}>
                        취소
                      </button>
                    </div>
                  </form>
                )}
              </div>
              {editing && itemEdit?.itemId !== item.tripItemId && (
                <div className="trip-schedule__stop-actions">
                  <button
                    type="button"
                    className="btn trip-schedule__stop-move"
                    aria-label="위로 이동"
                    disabled={busyId !== null || index === 0}
                    onClick={() => handleMove(index, -1)}
                  >
                    ↑
                  </button>
                  <button
                    type="button"
                    className="btn trip-schedule__stop-move"
                    aria-label="아래로 이동"
                    disabled={busyId !== null || index === selectedDay.items.length - 1}
                    onClick={() => handleMove(index, 1)}
                  >
                    ↓
                  </button>
                  <button
                    type="button"
                    className="btn trip-schedule__stop-remove"
                    disabled={busyId !== null}
                    onClick={() => startItemEdit(item)}
                  >
                    수정
                  </button>
                  <button
                    type="button"
                    className="btn trip-schedule__stop-remove"
                    disabled={busyId !== null}
                    onClick={() => handleDelete(item)}
                  >
                    삭제
                  </button>
                </div>
              )}
            </div>
            {routeLegs.has(item.tripItemId) && (
              <div className="trip-schedule__leg">
                🚗 {formatDistance(routeLegs.get(item.tripItemId).distanceMeters)} ·{' '}
                {formatDuration(routeLegs.get(item.tripItemId).durationSeconds)}
              </div>
            )}
            </Fragment>
          ))}

          {editing && (
            <div className="trip-schedule__search">
              <h3>장소 추가</h3>
              <form className="trip-schedule__search-form" onSubmit={handleSearch}>
                <input
                  type="text"
                  value={keyword}
                  onChange={(event) => setKeyword(event.target.value)}
                  placeholder="장소 이름으로 검색 (예: 경복궁)"
                  maxLength={50}
                />
                <button type="submit" className="btn btn-primary" disabled={searching}>
                  {searching ? '검색 중...' : '검색'}
                </button>
              </form>
              {editError && <p className="trip-schedule__search-error">{editError}</p>}
              <form className="trip-schedule__search-form trip-schedule__memo-form" onSubmit={handleAddMemo}>
                <input
                  type="text"
                  value={memoText}
                  onChange={(event) => setMemoText(event.target.value)}
                  placeholder="메모로 직접 입력 (예: 점심 후 카페에서 휴식)"
                  maxLength={MEMO_MAX_LENGTH}
                />
                <button type="submit" className="btn" disabled={busyId !== null || !memoText.trim()}>
                  메모 추가
                </button>
              </form>
              {searchResults?.length === 0 && <p className="trip-schedule__meta">검색 결과가 없습니다.</p>}
              {searchResults?.map((result) => {
                const addedCount = placeVisitCounts.get(result.contentId) ?? 0
                return (
                  <div key={result.contentId} className="trip-schedule__result">
                    <div className="trip-schedule__stop-body">
                      <p className="trip-schedule__stop-label">{result.category}</p>
                      <p className="trip-schedule__stop-name">{result.name}</p>
                      <p className="trip-schedule__meta">{result.address}</p>
                      {addedCount > 0 && (
                        <span className="badge badge-safe trip-schedule__added-badge">
                          이 날 {addedCount}회 추가됨
                        </span>
                      )}
                    </div>
                    <button
                      type="button"
                      className="btn"
                      disabled={busyId !== null}
                      onClick={() => handleAdd(result)}
                    >
                      {addedCount > 0 ? '또 추가' : '추가'}
                    </button>
                  </div>
                )
              })}
            </div>
          )}
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

      {!planning && (
        <div className="trip-schedule__danger-zone">
          <TripDeleteButton
            tripId={trip.tripId}
            title={trip.title}
            onDeleted={() => navigate('/mytrips/stats', { replace: true })}
          />
        </div>
      )}
    </div>
  )
}
