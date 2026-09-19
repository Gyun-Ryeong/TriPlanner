import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
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

export default function NewTrip() {
  const [selected, setSelected] = useState('jeju')
  const navigate = useNavigate()
  const selectedRegion = REGIONS.find((r) => r.id === selected)

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

      <div className="newtrip__footer">
        <button type="button" className="btn btn-primary" onClick={() => navigate('/schedule')}>
          {selectedRegion?.name} 선택 · 다음 단계로 진행 →
        </button>
      </div>
    </div>
  )
}
