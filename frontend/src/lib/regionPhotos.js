import { useEffect, useState } from 'react'
import { getRegionPhoto } from '../api/weather.js'

// 여행 지역(NewTrip 의 REGIONS 이름)별 대표 사진. 출처와 라이선스는 README '데이터 출처'에 적어 두었다
const REGION_PHOTOS = {
  '서울 특별시': '/images/regions/seoul.jpg',
  '경기도 / 인천': '/images/regions/gi.jpg',
  '강원도': '/images/regions/gangwon.jpg',
  '충청도': '/images/regions/chungcheong.jpg',
  '전라도': '/images/regions/jeolla.jpg',
  '경상도': '/images/regions/gyeongsang.jpg',
  '제주도': '/images/regions/jeju.jpg',
}

// 세부 지역(시)별 대표 사진. 서울은 권역 사진과 같아 따로 두지 않는다
const CITY_PHOTOS = {
  '인천': '/images/cities/incheon.jpg',
  '수원': '/images/cities/suwon.jpg',
  '가평': '/images/cities/gapyeong.jpg',
  '춘천': '/images/cities/chuncheon.jpg',
  '강릉': '/images/cities/gangneung.jpg',
  '속초': '/images/cities/sokcho.jpg',
  '대전': '/images/cities/daejeon.jpg',
  '청주': '/images/cities/cheongju.jpg',
  '천안': '/images/cities/cheonan.jpg',
  '태안': '/images/cities/taean.jpg',
  '광주': '/images/cities/gwangju.jpg',
  '전주': '/images/cities/jeonju.jpg',
  '여수': '/images/cities/yeosu.jpg',
  '목포': '/images/cities/mokpo.jpg',
  '부산': '/images/cities/busan.jpg',
  '대구': '/images/cities/daegu.jpg',
  '울산': '/images/cities/ulsan.jpg',
  '경주': '/images/cities/gyeongju.jpg',
  '안동': '/images/cities/andong.jpg',
  '제주': '/images/cities/jeju.jpg',
  '서귀포': '/images/cities/seogwipo.jpg',
}

// 사진이 없는 지역이면 null
export function regionPhoto(region) {
  return REGION_PHOTOS[region] ?? null
}

// 여행 목록에 보여줄 사진: 세부 지역(시)을 골랐고 그 도시 사진이 있으면 도시 사진, 아니면 권역 사진
export function tripPhoto(trip) {
  return CITY_PHOTOS[trip.city] ?? regionPhoto(trip.region)
}

// 사진 파일이 없는 시·군(성남, 곡성 등)은 서버에서 그 지역 관광지 사진(한국관광공사)을 받아 온다.
// 같은 지역은 한 번만 부르도록 화면을 옮겨 다녀도 결과를 기억한다
const remotePhotos = new Map()

function loadRemotePhoto(city, region) {
  const key = `${city}|${region}`
  if (!remotePhotos.has(key)) {
    remotePhotos.set(
      key,
      getRegionPhoto(city, region)
        .then((data) => (data?.image ? { src: data.image, credit: data.credit, title: data.title } : null))
        .catch(() => {
          remotePhotos.delete(key) // 실패는 기억하지 않아 다음에 다시 시도
          return null
        }),
    )
  }
  return remotePhotos.get(key)
}

// { src, credit, title } | null. 받아 오는 동안과 못 찾았을 때는 권역 사진
export function useTripPhoto(trip) {
  const local = CITY_PHOTOS[trip.city]
  const needsRemote = Boolean(trip.city) && !local
  const key = `${trip.city}|${trip.region}`
  // 어느 지역의 결과인지 함께 들고 있어서, 다른 여행으로 바뀌면 이전 사진을 보여주지 않는다
  const [remote, setRemote] = useState({ key: null, photo: null })

  useEffect(() => {
    if (!needsRemote) return undefined
    let cancelled = false
    loadRemotePhoto(trip.city, trip.region).then((photo) => {
      if (!cancelled) setRemote({ key: `${trip.city}|${trip.region}`, photo })
    })
    return () => {
      cancelled = true
    }
  }, [needsRemote, trip.city, trip.region])

  if (local) return { src: local }
  if (needsRemote && remote.key === key && remote.photo) return remote.photo
  const fallback = regionPhoto(trip.region)
  return fallback ? { src: fallback } : null
}
