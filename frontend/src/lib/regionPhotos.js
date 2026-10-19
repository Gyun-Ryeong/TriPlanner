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
