import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { WEEKDAYS, buildCells, shiftMonth, todayIso } from '../lib/festivalCalendar.js'
import { useHolidays } from '../lib/useHolidays.js'
import './TripCalendar.css'

const BAR_COLORS = ['#3b5bdb', '#e8590c', '#2f9e44', '#ae3ec9', '#0c8599', '#d6336c']

// 한 달 달력을 7칸씩 끊은 주(週) 목록으로 만든다 (마지막 주는 빈 칸으로 채움)
function buildWeeks(year, month) {
  const cells = buildCells(year, month)
  while (cells.length % 7 !== 0) cells.push(null)
  const weeks = []
  for (let i = 0; i < cells.length; i += 7) weeks.push(cells.slice(i, i + 7))
  return weeks
}

// 한 주 안에서 여행마다 가로 막대(시작 칸~끝 칸)를 정하고, 겹치는 여행은 아래 줄로 쌓는다
function layoutWeek(week, trips) {
  const days = week.filter(Boolean)
  const first = days[0]
  const last = days[days.length - 1]
  const segments = trips
    .filter((trip) => trip.startDate <= last && trip.endDate >= first)
    .map((trip) => {
      const segStart = trip.startDate > first ? trip.startDate : first
      const segEnd = trip.endDate < last ? trip.endDate : last
      return {
        trip,
        from: week.indexOf(segStart),
        to: week.indexOf(segEnd),
        continuesBefore: trip.startDate < segStart,
        continuesAfter: trip.endDate > segEnd,
      }
    })
    .sort((a, b) => a.from - b.from || b.to - a.to)

  const laneEnds = []
  segments.forEach((seg) => {
    let lane = laneEnds.findIndex((end) => end < seg.from)
    if (lane === -1) lane = laneEnds.length
    laneEnds[lane] = seg.to
    seg.lane = lane
  })
  return { segments, laneCount: laneEnds.length }
}

// 내 여행 달력: 여행 기간이 시작일부터 종료일까지 한 줄로 이어진 막대로 보인다
export default function TripCalendar({ trips }) {
  const today = todayIso()
  const [ym, setYm] = useState(() => ({ year: Number(today.slice(0, 4)), month: Number(today.slice(5, 7)) }))

  const weeks = useMemo(() => buildWeeks(ym.year, ym.month), [ym])
  const holidays = useHolidays(ym.year, ym.month)
  // 여행마다 색을 하나씩 배정한다 (목록 순서 기준이라 달을 넘겨도 같은 색)
  const colorOf = useMemo(() => new Map(trips.map((t, i) => [t.tripId, BAR_COLORS[i % BAR_COLORS.length]])), [trips])

  const monthPrefix = `${ym.year}-${String(ym.month).padStart(2, '0')}-`
  const monthStart = `${monthPrefix}01`
  const monthEnd = `${monthPrefix}31`
  const hasTripThisMonth = trips.some((t) => t.startDate <= monthEnd && t.endDate >= monthStart)

  return (
    <div className="trip-cal">
      <div className="trip-cal__nav">
        <button type="button" className="btn btn-sm" aria-label="이전 달" onClick={() => setYm((c) => shiftMonth(c.year, c.month, -1))}>‹</button>
        <h3 className="trip-cal__month">{ym.year}년 {ym.month}월</h3>
        <button type="button" className="btn btn-sm" aria-label="다음 달" onClick={() => setYm((c) => shiftMonth(c.year, c.month, 1))}>›</button>
        <button
          type="button"
          className="btn btn-sm trip-cal__today"
          onClick={() => setYm({ year: Number(today.slice(0, 4)), month: Number(today.slice(5, 7)) })}
        >
          오늘
        </button>
      </div>

      <div className="trip-cal__weekdays" aria-hidden="true">
        {WEEKDAYS.map((w, i) => (
          <span key={w} className={i === 0 ? 'trip-cal__sun' : i === 6 ? 'trip-cal__sat' : ''}>{w}</span>
        ))}
      </div>

      <div className="trip-cal__weeks">
        {weeks.map((week, weekIndex) => {
          const { segments, laneCount } = layoutWeek(week, trips)
          return (
            <div
              key={weekIndex}
              className="trip-cal__week"
              style={{ gridTemplateRows: `26px repeat(${laneCount}, 22px) minmax(10px, 1fr)` }}
            >
              {week.map((iso, i) =>
                iso ? (
                  <span
                    key={iso}
                    className={`trip-cal__cell${iso === today ? ' trip-cal__cell--today' : ''}`}
                    style={{ gridColumn: i + 1, gridRow: '1 / -1' }}
                  >
                    <span className={`trip-cal__date${i === 0 || holidays[iso] ? ' trip-cal__sun' : i === 6 ? ' trip-cal__sat' : ''}`}>
                      {Number(iso.slice(8))}
                    </span>
                    {holidays[iso] && <span className="trip-cal__holiday" title={holidays[iso]}>{holidays[iso]}</span>}
                  </span>
                ) : (
                  <span key={`blank-${i}`} className="trip-cal__cell trip-cal__cell--blank" style={{ gridColumn: i + 1, gridRow: '1 / -1' }} />
                )
              )}
              {segments.map((seg) => (
                <Link
                  key={seg.trip.tripId}
                  to={`/schedule/${seg.trip.tripId}`}
                  className={[
                    'trip-cal__bar',
                    seg.continuesBefore ? 'trip-cal__bar--cont-before' : '',
                    seg.continuesAfter ? 'trip-cal__bar--cont-after' : '',
                  ].join(' ')}
                  style={{
                    gridColumn: `${seg.from + 1} / ${seg.to + 2}`,
                    gridRow: seg.lane + 2,
                    background: colorOf.get(seg.trip.tripId),
                  }}
                  title={`${seg.trip.title} (${seg.trip.startDate} ~ ${seg.trip.endDate})`}
                >
                  {seg.trip.title}
                </Link>
              ))}
            </div>
          )
        })}
      </div>

      {!hasTripThisMonth && <p className="trip-cal__empty">이 달에는 여행이 없어요.</p>}
    </div>
  )
}
