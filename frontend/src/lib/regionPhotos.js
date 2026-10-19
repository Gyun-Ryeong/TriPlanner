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

// 사진이 없는 지역이면 null
export function regionPhoto(region) {
  return REGION_PHOTOS[region] ?? null
}
