import { GRADE_CLASS } from '../lib/weatherSummary.js'

// 대기질 한 항목(등급 + 수치). 값이 없으면 '-'
export default function AirCell({ metric, unit = '' }) {
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
