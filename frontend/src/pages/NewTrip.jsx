import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { createTrip } from '../api/trips.js'
import './NewTrip.css'

const REGIONS = [
  { id: 'seoul', name: '서울 특별시', desc: '경복궁, N서울타워, 한강공원 고층 도시 투어', area: 'seoul' },
  { id: 'gi', name: '경기도 / 인천', desc: '수원화성, 에버랜드, 송도 센트럴파크 근교 쉼터', area: 'gi' },
  { id: 'gangwon', name: '강원도', desc: '설악산, 경포대 해변, 커피거리 자연 힐링', area: 'gangwon' },
  { id: 'chungcheong', name: '충청도', desc: '태안 신두리 사구, 안면도, 단양 국립공원 역사 기행', area: 'chungcheong' },
  { id: 'jeolla', name: '전라도', desc: '전주 한옥마을, 순천만 국가정원, 여수 밤바다', area: 'jeolla' },
  { id: 'gyeongsang', name: '경상도', desc: '경주 첨성대, 부산 해운대 해수욕장, 해운대 해변열차', area: 'gyeongsang' },
  { id: 'jeju', name: '제주도', desc: '한라산 백록담, 올레길 코스, 곽지 해수욕장 푸른 바다', area: 'jeju' },
]

function todayPlus(days) {
  const date = new Date()
  date.setDate(date.getDate() + days)
  return date.toISOString().slice(0, 10)
}

export default function NewTrip() {
  const [selected, setSelected] = useState('jeju')
  const [title, setTitle] = useState('')
  const [startDate, setStartDate] = useState(todayPlus(0))
  const [endDate, setEndDate] = useState(todayPlus(2))
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const navigate = useNavigate()
  const selectedRegion = REGIONS.find((r) => r.id === selected)

  async function handleSubmit() {
    if (!title.trim()) {
      setError('여행 제목을 입력해주세요.')
      return
    }
    if (endDate < startDate) {
      setError('종료일은 시작일보다 빠를 수 없습니다.')
      return
    }

    setError('')
    setSubmitting(true)

    try {
      const trip = await createTrip({ title, region: selectedRegion.name, startDate, endDate })
      navigate(`/schedule/${trip.tripId}`)
    } catch (err) {
      setError(err.message ?? '여행 생성에 실패했습니다.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="newtrip">
      <h1 className="newtrip__title">새 여행 생성하기</h1>
      <p className="newtrip__subtitle">국내 여행지를 선택해주세요</p>

      <div className="newtrip__body">
        <div className="card newtrip__map-card">
          <p className="newtrip__map-label">대한민국 지도</p>
          <div className="newtrip__map">
            {REGIONS.filter((r) => r.id !== 'jeju').map((r) => (
              <button
                key={r.id}
                type="button"
                className={`newtrip__map-region newtrip__map-region--${r.area} ${selected === r.id ? 'newtrip__map-region--selected' : ''}`}
                onClick={() => setSelected(r.id)}
              >
                {r.name.split(' ')[0].replace('/', '')}
              </button>
            ))}
          </div>
          <button
            type="button"
            className={`newtrip__jeju ${selected === 'jeju' ? 'newtrip__jeju--selected' : ''}`}
            onClick={() => setSelected('jeju')}
          >
            제주
          </button>
        </div>

        <div className="newtrip__list">
          {REGIONS.map((r) => (
            <button
              key={r.id}
              type="button"
              className={`newtrip__option ${selected === r.id ? 'newtrip__option--selected' : ''}`}
              onClick={() => setSelected(r.id)}
            >
              <div>
                <p className="newtrip__option-name">{r.name}</p>
                <p className="newtrip__option-desc">{r.desc}</p>
              </div>
              {selected === r.id && <span className="newtrip__check">✓</span>}
            </button>
          ))}
        </div>
      </div>

      <div className="card newtrip__details">
        <div className="newtrip__field">
          <label htmlFor="trip-title">여행 제목</label>
          <input
            id="trip-title"
            type="text"
            placeholder="예: 경주 힐링 여행"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
        </div>

        <div className="newtrip__field">
          <label htmlFor="trip-start">시작일</label>
          <input
            id="trip-start"
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
          />
        </div>

        <div className="newtrip__field">
          <label htmlFor="trip-end">종료일</label>
          <input
            id="trip-end"
            type="date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
          />
        </div>
      </div>

      {error && <p className="newtrip__error">{error}</p>}

      <div className="newtrip__footer">
        <button type="button" className="btn btn-primary" disabled={submitting} onClick={handleSubmit}>
          {submitting ? '생성 중...' : `${selectedRegion?.name} 선택 · 다음 단계로 진행 →`}
        </button>
      </div>
    </div>
  )
}
