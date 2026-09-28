import { useEffect, useState } from 'react'
import { ComposableMap, Geographies, Geography } from '@vnedyalk0v/react19-simple-maps'

// 지도 경계 데이터(public/korea-provinces.json) 출처: 통계청 SGIS,
// https://github.com/southkorea/southkorea-maps (공공누리 제1유형)

const PROVINCE_TO_REGION = {
  '서울특별시': 'seoul',
  '인천광역시': 'gi',
  '경기도': 'gi',
  '강원도': 'gangwon',
  '강원특별자치도': 'gangwon',
  '대전광역시': 'chungcheong',
  '세종특별자치시': 'chungcheong',
  '충청북도': 'chungcheong',
  '충청남도': 'chungcheong',
  '광주광역시': 'jeolla',
  '전라북도': 'jeolla',
  '전북특별자치도': 'jeolla',
  '전라남도': 'jeolla',
  '대구광역시': 'gyeongsang',
  '부산광역시': 'gyeongsang',
  '울산광역시': 'gyeongsang',
  '경상북도': 'gyeongsang',
  '경상남도': 'gyeongsang',
  '제주특별자치도': 'jeju',
}

export default function KoreaMap({ selected, onSelect }) {
  const [topology, setTopology] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false

    fetch('/korea-provinces.json')
      .then((res) => res.json())
      .then((data) => {
        if (!cancelled) setTopology(data)
      })
      .catch(() => {
        if (!cancelled) setError('지도를 불러오지 못했습니다.')
      })

    return () => {
      cancelled = true
    }
  }, [])

  if (error) {
    return <p className="newtrip__map-error">{error}</p>
  }

  if (!topology) {
    return <p className="newtrip__map-error">지도를 불러오는 중...</p>
  }

  return (
    <ComposableMap
      projection="geoMercator"
      projectionConfig={{ center: [127.8, 36], scale: 5000 }}
      width={500}
      height={650}
    >
      <Geographies geography={topology}>
        {({ geographies }) =>
          geographies.map((geo) => {
            const regionId = PROVINCE_TO_REGION[geo.properties.name]
            const isSelected = regionId === selected

            return (
              <Geography
                key={geo.rsmKey}
                geography={geo}
                onClick={() => regionId && onSelect(regionId)}
                style={{
                  default: {
                    fill: isSelected ? 'var(--color-primary)' : '#dbe3f5',
                    stroke: '#fff',
                    strokeWidth: 0.75,
                    outline: 'none',
                    cursor: 'pointer',
                  },
                  hover: {
                    fill: isSelected ? 'var(--color-primary)' : '#8fa8ff',
                    stroke: '#fff',
                    strokeWidth: 0.75,
                    outline: 'none',
                    cursor: 'pointer',
                  },
                  pressed: {
                    fill: 'var(--color-primary-dark)',
                    stroke: '#fff',
                    strokeWidth: 0.75,
                    outline: 'none',
                  },
                }}
              />
            )
          })
        }
      </Geographies>
    </ComposableMap>
  )
}
