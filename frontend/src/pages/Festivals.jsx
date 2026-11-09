import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { getFestivalDetail, getFestivalMonth } from '../api/festivals.js'
import {
  SIDO_LIST,
  WEEKDAYS,
  buildCells,
  periodText,
  shiftMonth,
  statusOf,
  todayIso,
} from '../lib/festivalCalendar.js'
import { matchesQuery } from '../lib/hangul.js'
import { useHolidays } from '../lib/useHolidays.js'
import './Festivals.css'

const SIDO_KEY = 'triplanner_festival_sido'

function loadSido() {
  try {
    const saved = localStorage.getItem(SIDO_KEY)
    if (SIDO_LIST.includes(saved)) return saved
  } catch {
    // 저장소를 못 쓰는 환경이면 기본값을 쓴다
  }
  return '서울'
}

// 지역 선택: 버튼을 한 줄로 깔아 두고, 넘치면 옆으로 밀어 보거나(모바일) 양끝 화살표로 이동한다(PC)
function SidoPicker({ value, onChange }) {
  const scrollRef = useRef(null)
  const [edge, setEdge] = useState({ start: true, end: false })
  const [query, setQuery] = useState('')

  const updateEdge = useCallback(() => {
    const el = scrollRef.current
    if (!el) return
    setEdge({
      start: el.scrollLeft <= 1,
      end: el.scrollLeft + el.clientWidth >= el.scrollWidth - 1,
    })
  }, [])

  useEffect(() => {
    updateEdge()
    window.addEventListener('resize', updateEdge)
    return () => window.removeEventListener('resize', updateEdge)
  }, [updateEdge])

  // 처음 열 때 선택된 지역이 보이는 위치로 맞춘다
  useEffect(() => {
    const el = scrollRef.current
    const active = el?.querySelector('[aria-pressed="true"]')
    if (el && active) {
      el.scrollLeft = active.offsetLeft - (el.clientWidth - active.offsetWidth) / 2
      updateEdge()
    }
    // 첫 화면에서 한 번만 맞춘다
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function scrollBy(direction) {
    const el = scrollRef.current
    if (el) el.scrollBy({ left: direction * el.clientWidth * 0.7, behavior: 'smooth' })
  }

  const names = SIDO_LIST.filter((name) => matchesQuery(name, query))

  // 검색어가 바뀌면 목록 길이가 달라지므로 맨 앞으로 돌려놓고 화살표 상태를 다시 계산한다
  function changeQuery(next) {
    setQuery(next)
    const el = scrollRef.current
    if (el) el.scrollLeft = 0
    requestAnimationFrame(updateEdge)
  }

  return (
    <div className="festivals__sido" role="group" aria-label="지역 선택">
      <input
        type="search"
        className="festivals__sido-search"
        value={query}
        onChange={(e) => changeQuery(e.target.value)}
        placeholder="지역 검색 (예: ㅅㅇ)"
        aria-label="지역 검색 (초성 가능)"
      />
      <button
        type="button"
        className="festivals__sido-arrow"
        aria-label="왼쪽 지역 보기"
        disabled={edge.start}
        onClick={() => scrollBy(-1)}
      >
        ‹
      </button>
      <div className="festivals__sido-scroll" ref={scrollRef} onScroll={updateEdge}>
        {names.map((name) => (
          <button
            key={name}
            type="button"
            className={`festivals__sido-chip${name === value ? ' festivals__sido-chip--active' : ''}`}
            aria-pressed={name === value}
            onClick={() => onChange(name)}
          >
            {name}
          </button>
        ))}
        {names.length === 0 && <span className="festivals__sido-none">맞는 지역이 없어요</span>}
      </div>
      <button
        type="button"
        className="festivals__sido-arrow"
        aria-label="오른쪽 지역 보기"
        disabled={edge.end}
        onClick={() => scrollBy(1)}
      >
        ›
      </button>
    </div>
  )
}

function StatusBadge({ start, end }) {
  const { label, tone } = statusOf(start, end)
  return <span className={`festivals__status festivals__status--${tone}`}>{label}</span>
}

function Poster({ src, title }) {
  const [broken, setBroken] = useState(false)
  if (!src || broken) return <div className="festivals__poster festivals__poster--empty" aria-hidden="true">축제</div>
  return (
    <img
      className="festivals__poster"
      src={src}
      alt={`${title} 포스터`}
      loading="lazy"
      onError={() => setBroken(true)}
    />
  )
}

function DayList({ day, ids, byId, onPick }) {
  if (!day) {
    return <p className="festivals__hint">달력에서 날짜를 누르면 그날 열리는 축제를 볼 수 있어요.</p>
  }
  const title = `${Number(day.slice(5, 7))}월 ${Number(day.slice(8, 10))}일`
  if (ids.length === 0) {
    return (
      <>
        <h2 className="festivals__panel-title">{title}</h2>
        <p className="festivals__hint">이 날 열리는 축제가 없어요.</p>
      </>
    )
  }
  return (
    <>
      <h2 className="festivals__panel-title">
        {title} <span className="festivals__count">축제 {ids.length}개</span>
      </h2>
      <ul className="festivals__list">
        {ids.map((id, index) => {
          const f = byId.get(id)
          if (!f) return null
          return (
            <li key={id}>
              <button type="button" className="festivals__row" onClick={() => onPick(id)}>
                <Poster src={f.image} title={f.title} />
                <span className="festivals__row-body">
                  <span className="festivals__row-title">
                    {f.title}
                    {ids.length > 1 && index === 0 && <span className="festivals__lead">대표</span>}
                  </span>
                  <span className="festivals__row-meta">{periodText(f.start, f.end)}</span>
                  <span className="festivals__row-meta">{f.addr}</span>
                </span>
                <StatusBadge start={f.start} end={f.end} />
              </button>
            </li>
          )
        })}
      </ul>
    </>
  )
}

function InfoRow({ label, value }) {
  if (!value) return null
  return (
    <div className="festivals__info-row">
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  )
}

function Detail({ summary, state, onBack }) {
  const data = state?.data
  const failed = state?.error
  const title = data?.title || summary?.title || ''
  const start = data?.start || summary?.start
  const end = data?.end || summary?.end
  const [primary, ...others] = data?.links ?? []

  return (
    <div className="festivals__detail">
      <button type="button" className="festivals__back" onClick={onBack}>← 목록으로</button>
      <Poster src={data?.image || summary?.image} title={title} />
      <h2 className="festivals__detail-title">
        {title} <StatusBadge start={start} end={end} />
      </h2>
      {!state && <p className="festivals__hint">자세한 내용을 불러오는 중이에요…</p>}
      {failed && <p className="festivals__error">{failed}</p>}

      <dl className="festivals__info">
        <InfoRow label="기간" value={periodText(start, end)} />
        <InfoRow label="시간" value={data?.playTime} />
        <InfoRow label="장소" value={data?.place || data?.addr || summary?.addr} />
        <InfoRow label="주소" value={data?.place ? data?.addr : ''} />
        <InfoRow label="요금" value={data?.fee} />
        <InfoRow label="주최" value={data?.sponsor} />
        <InfoRow label="문의" value={data?.tel} />
      </dl>

      {data?.overview && <p className="festivals__overview">{data.overview}</p>}
      {data?.program && (
        <>
          <h3 className="festivals__sub">프로그램</h3>
          <p className="festivals__overview">{data.program}</p>
        </>
      )}

      {primary && (
        <div className="festivals__links">
          <a className="btn btn-primary" href={primary.url} target="_blank" rel="noopener noreferrer">
            {primary.label} ↗
          </a>
          {primary.kind === 'news' && primary.title && (
            <p className="festivals__link-note">{primary.title}</p>
          )}
          {others.map((link) => (
            <a key={link.kind} className="festivals__link" href={link.url} target="_blank" rel="noopener noreferrer">
              {link.label} ↗
            </a>
          ))}
        </div>
      )}
    </div>
  )
}

export default function Festivals() {
  const today = todayIso()
  const [sido, setSido] = useState(loadSido)
  const [ym, setYm] = useState(() => ({ year: Number(today.slice(0, 4)), month: Number(today.slice(5, 7)) }))
  const [pickedDay, setPickedDay] = useState(null)
  const [selectedId, setSelectedId] = useState(null)
  const [result, setResult] = useState(null) // { key, data, error }
  const [detail, setDetail] = useState(null) // { id, data, error }

  const key = `${sido}|${ym.year}|${ym.month}`

  useEffect(() => {
    let cancelled = false
    getFestivalMonth(sido, ym.year, ym.month)
      .then((data) => !cancelled && setResult({ key, data }))
      .catch((e) => !cancelled && setResult({ key, error: e.message || '축제 정보를 불러오지 못했어요.' }))
    return () => {
      cancelled = true
    }
  }, [key, sido, ym.year, ym.month])

  useEffect(() => {
    if (!selectedId) return undefined
    let cancelled = false
    getFestivalDetail(selectedId)
      .then((data) => !cancelled && setDetail({ id: selectedId, data }))
      .catch((e) => !cancelled && setDetail({ id: selectedId, error: e.message || '자세한 내용을 불러오지 못했어요.' }))
    return () => {
      cancelled = true
    }
  }, [selectedId])

  const loading = !result || result.key !== key
  const data = loading ? null : result.data
  const unavailable = !loading && (result.error || data?.available === false)

  const byId = useMemo(() => new Map((data?.festivals ?? []).map((f) => [f.contentId, f])), [data])
  const cells = useMemo(() => buildCells(ym.year, ym.month), [ym])
  const holidays = useHolidays(ym.year, ym.month)

  const monthPrefix = `${ym.year}-${String(ym.month).padStart(2, '0')}-`
  const activeDay = pickedDay && pickedDay.startsWith(monthPrefix)
    ? pickedDay
    : (today.startsWith(monthPrefix) ? today : null)
  const dayIds = activeDay ? (data?.days?.[activeDay] ?? []) : []

  function changeSido(next) {
    setSido(next)
    setSelectedId(null)
    try {
      localStorage.setItem(SIDO_KEY, next)
    } catch {
      // 저장하지 못해도 화면은 그대로 동작한다
    }
  }

  function moveMonth(delta) {
    setYm((cur) => shiftMonth(cur.year, cur.month, delta))
    setPickedDay(null)
    setSelectedId(null)
  }

  function goToday() {
    setYm({ year: Number(today.slice(0, 4)), month: Number(today.slice(5, 7)) })
    setPickedDay(today)
    setSelectedId(null)
  }

  return (
    <div className="festivals">
      <div className="page-head">
        <div>
          <p className="page-eyebrow">FESTIVAL</p>
          <h1 className="page-title">축제 달력</h1>
          <p className="page-subtitle">
            같은 날 축제가 여럿이면 뉴스에서 더 많이 다뤄진 축제를 대표로 보여드려요.
          </p>
        </div>
      </div>

      <SidoPicker value={sido} onChange={changeSido} />

      <div className="festivals__layout">
        <section className="card festivals__calendar" aria-label="축제 달력">
          <div className="festivals__nav">
            <button type="button" className="btn btn-sm" onClick={() => moveMonth(-1)} aria-label="이전 달">‹</button>
            <h2 className="festivals__month">{ym.year}년 {ym.month}월</h2>
            <button type="button" className="btn btn-sm" onClick={() => moveMonth(1)} aria-label="다음 달">›</button>
            <button type="button" className="btn btn-sm festivals__today-btn" onClick={goToday}>오늘</button>
          </div>

          <div className="festivals__grid festivals__weekdays" aria-hidden="true">
            {WEEKDAYS.map((w, i) => (
              <span key={w} className={i === 0 ? 'festivals__sun' : i === 6 ? 'festivals__sat' : ''}>{w}</span>
            ))}
          </div>

          <div className={`festivals__grid festivals__cells ${loading ? 'festivals__cells--loading' : ''}`}>
            {cells.map((iso, i) => {
              if (!iso) return <span key={`blank-${i}`} className="festivals__cell festivals__cell--blank" />
              const ids = data?.days?.[iso] ?? []
              const lead = ids.length ? byId.get(ids[0]) : null
              const weekday = (i % 7)
              const holiday = holidays[iso]
              return (
                <button
                  key={iso}
                  type="button"
                  className={[
                    'festivals__cell',
                    iso === today ? 'festivals__cell--today' : '',
                    iso === activeDay ? 'festivals__cell--active' : '',
                  ].join(' ')}
                  onClick={() => {
                    setPickedDay(iso)
                    setSelectedId(null)
                  }}
                  aria-label={`${Number(iso.slice(8))}일${holiday ? `, ${holiday}` : ''}${ids.length ? `, 축제 ${ids.length}개` : ''}`}
                >
                  <span className={`festivals__date ${weekday === 0 || holiday ? 'festivals__sun' : weekday === 6 ? 'festivals__sat' : ''}`}>
                    {Number(iso.slice(8))}
                  </span>
                  {holiday && <span className="festivals__holiday" title={holiday}>{holiday}</span>}
                  {lead && <span className="festivals__chip" title={lead.title}>{lead.title}</span>}
                  {ids.length > 1 && <span className="festivals__more">+{ids.length - 1}</span>}
                </button>
              )
            })}
          </div>

          {loading && <p className="festivals__status-line">축제 정보를 불러오는 중이에요… (처음엔 몇 초 걸릴 수 있어요)</p>}
          {unavailable && (
            <p className="festivals__status-line festivals__status-line--error">
              축제 정보를 불러오지 못했어요. 잠시 뒤 다시 시도해 주세요.
            </p>
          )}
          {!loading && !unavailable && data?.festivals?.length === 0 && (
            <p className="festivals__status-line">{sido}에는 이 달에 등록된 축제가 없어요.</p>
          )}
        </section>

        <aside className="card festivals__panel" aria-live="polite">
          {selectedId ? (
            <Detail
              summary={byId.get(selectedId)}
              state={detail?.id === selectedId ? detail : null}
              onBack={() => setSelectedId(null)}
            />
          ) : (
            <DayList day={activeDay} ids={dayIds} byId={byId} onPick={setSelectedId} />
          )}
        </aside>
      </div>
    </div>
  )
}
