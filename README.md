# TriPlanner

국내 여행의 모든 순간을 더 안전하고 자유롭게 — 맞춤 일정, 실시간 여행 알림, AI 여행 챗봇을 제공하는 국내 여행 플래너 서비스입니다.

## 팀원

- 이동희
- 김령균
- 이시우

## 주요 기능

- **여행 일정 관리**: 지역 선택 후 일차별 동선·일정 생성 및 수정, 지도와 길찾기
- **AI 여행 챗봇**: 최신 여행 정보 기반으로 일정·맛집·숙소·축제 등을 추천 (RAG 기반)
- **실시간 여행 알림**: 여행 3일 전부터 여행지의 날씨·대기질(미세먼지)·기상특보를 확인해 주의/참고 알림 제공 (기상청·에어코리아 기반)
- **출발 전 준비**: 여행에 맞춘 체크리스트와 준비 알림
- **내 여행 관리**: 프로필, 여행 목록·통계, 다가오는 여행의 알림 확인

## 기술 스택

| 영역 | 기술 |
| --- | --- |
| Frontend | React 19, Vite, React Router |
| Backend | Java 25, Spring Boot 4.1 (Maven, Spring Data JPA, Spring Security + JWT) |
| AI 챗봇 | Python, FastAPI, ChromaDB, Ollama (로컬 LLM) |
| Database | MariaDB |
| 형상관리 | Git / GitHub |

## 폴더 구조

```
TriPlanner/
├── frontend/       # React 프론트엔드
├── backend/        # Spring Boot 백엔드
├── rag_project/    # AI 여행 챗봇 (Python, FastAPI + Ollama)
└── README.md
```

프론트엔드가 백엔드(`/api`)를 부르고, 챗봇 요청은 백엔드를 거쳐 `rag_project` 서버로 전달됩니다.

## 구현된 기능

- **회원/인증**: 회원가입(필수·선택 약관 동의 포함)/로그인(JWT), 프로필 수정(닉네임·전화번호·비밀번호 변경), 여행 알림·일정 변경 및 준비 알림 켜기/끄기, 마케팅 정보 수신 동의 철회. 회원 탈퇴(비밀번호와 확인 문구 입력)는 14일간 보관한 뒤 회원과 관련 데이터를 파기하며, 그 전에는 관리자가 복구할 수 있습니다.
- **여행 일정**: 지역(지도나 오른쪽 목록에서 도 단위로 선택, 아래 드롭다운에서 세부 지역(시)까지 선택 가능)·날짜로 여행 생성, 일차별 일정 입력 화면과 조회 화면 분리, 장소 검색(네이버 지역 검색)·메모 추가/삭제, 여행 삭제. 일정 수정 중에는 마지막 일차를 하나씩 추가·삭제해 여행 일수를 늘이거나 줄일 수 있고(최대 31일), 일정이 들어 있는 일차를 지울 때는 한 번 더 확인합니다. 여행 목록(여행 일정 탭)에는 지역 대표 사진이 함께 표시됩니다.
- **지도/길찾기**: 네이버 지도에 장소 마커와 동선 표시, 하루 동선의 자동차(네이버 Directions) / 도보(Tmap 보행자 경로, 장소 사이 구간별 호출) 길찾기.
- **실시간 알림**: 알림 탭은 내가 여행 가는 지역(예정·진행 중인 여행의 지역)의 날씨·대기질·기상특보를 작은 카드로 가장 먼저 보여주고(세부 지역을 고른 여행은 그 도시 기준 날씨), '전체 지역 날씨·대기질·특보 보기' 버튼을 누르면 다른 지역도 펼쳐 볼 수 있습니다(예정된 여행이 없으면 처음부터 전체 지역을 보여줍니다). 권역(서울/경기·인천/강원/충청/전라/경상/제주)별 날씨(기상청 단기예보, 기온 범위 + 가장 주의할 도시, '도시별 보기'로 도시별 확인), 기상특보 현황, 권역별 대기질 현황(에어코리아, 시도별 값 펼쳐 보기). 여행 시작이 3일 이내이면 날씨·대기질 예보·기상특보로 **주의/참고** 알림을 만들어 헤더 종 아이콘, Home, 알림 탭, 일정 화면에 보여줍니다. (예보는 여행일 기준 3일 이내만 제공)
- **출발 전 체크리스트**: 여행을 처음 열 때 기간(당일/숙박)·지역(제주 항공·렌터카)·출발 계절에 맞는 준비 항목이 D-7(예약)·D-3(확인)·D-1(짐)·출발 당일 기한으로 자동 생성됩니다. Home 카드에서 진행률과 지금 챙길 항목을 체크하고, `/trips/:id/checklist` 에서 전체 보기·직접 추가·삭제를 합니다. 이미 기한이 지난 항목은 만들거나 보여주지 않습니다. Home·내 프로필의 '다가오는 여행'은 종료일이 오늘 이후인 가장 빠른 여행입니다.
- **일정 변경·준비 알림**: 아직 출발하지 않은 여행에 대해 체크리스트에서 오늘까지인 미완료 항목, 출발 7일 이내인데 비어 있는 일차를 알려줍니다. 요청 때마다 계산하며 헤더 종·Home·알림 탭에 여행 위험 알림과 함께 표시됩니다. 앱 안 알림만 제공합니다.
- **AI 여행 챗봇(RAG)**: 챗봇 페이지와 플로팅 위젯에서 대화로 일정·맛집·숙소·축제·지역 소식을 받습니다. 페이지와 위젯은 같은 대화를 이어갑니다. 대화는 목록(페이지는 왼쪽, 위젯은 '대화 목록' 화면)으로 보관되며 이 브라우저(localStorage)에만 저장됩니다. 📌로 고정하지 않은 대화는 만든 지 24시간 뒤 사라지고(전체 10개, 고정 최대 5개), 제목은 첫 질문으로 정해지며 ✏️로 바꿀 수 있습니다. 챗봇이 만든 일정은 '내 여행에 저장' 버튼으로 내 여행에 저장되고(장소·시간·메모 포함), 일정 화면의 '일정 수정'에서 시간·메모 수정, 순서 변경, 추가·삭제를 할 수 있습니다. 자세한 기능은 [`rag_project/README.md`](rag_project/README.md) 참고.
- **관리자 페이지**(`/admin`, 관리자 계정만): 챗봇 서버 상태, 챗봇 개발자 모드(응답 속도·일정 품질 지표 표시), 회원 목록과 탈퇴 회원 복구, 챗봇 호출 오류 기록(30일 보관).
- **공통 화면**: 로그인 상태에 따른 라우트 보호, 플로팅 챗봇 위젯.

## 알려진 한계

- **네이버 로그인**: 코드는 있으나 실제 로그인 흐름은 아직 검증되지 않았습니다. 카카오·구글 버튼은 화면만 있습니다. 네이버로 가입한 회원은 비밀번호가 없어 지금은 회원 탈퇴를 할 수 없습니다.
- **알림 발송**: 문자·이메일 등 외부 발송은 없고 앱 안 알림만 제공합니다.
- **예보 기간**: 3일을 넘는 날짜의 예보(기상청 중기예보)는 연동하지 않았습니다.

## 데이터 출처

- **대한민국 시도 경계 지도 데이터** (`frontend/public/korea-provinces.json`): 통계청 통계지리정보서비스(SGIS)가 공개한 자료를 [southkorea/southkorea-maps](https://github.com/southkorea/southkorea-maps) 저장소가 정리해 배포한 것을 사용했습니다. [공공누리 제1유형](http://www.kogl.or.kr/info/license.do) 라이선스.
- **여행 목록 지역 대표 사진** (`frontend/public/images/regions/`): 위키미디어 커먼즈 (640px 축소본). 이용 조건에 따라 출처를 밝힙니다.
  - 서울: Gyeonghoeru at Gyeongbokgung Palace — Frank Schulenburg, [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)
  - 경기도/인천: Hwaseong Fortress 01 — Bernard Gagnon, CC0
  - 강원도: Seoraksan National Park panorama 3 — kallerna, [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)
  - 충청도: Sindu sandhills image 3 — Jjw, [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)
  - 전라도: Suncheon Bay Ecological Park — Jakob Reichmann, [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/)
  - 경상도: Haeundae Beach in Busan — StephNurnberg, [CC BY 2.0](https://creativecommons.org/licenses/by/2.0/)
  - 제주도: Seongsan Ilchulbong 01 — Bernard Gagnon, CC0
- **여행 목록 세부 지역(시) 대표 사진** (`frontend/public/images/cities/`): 위키미디어 커먼즈 (640px 축소본). 서울은 위의 서울 사진을 같이 씁니다.
  - 인천: Songdo Convensia and Central Park View — Ken Eckert, CC BY-SA 4.0
  - 수원: Paldalmun hwaseong suwon — Kbarends, CC BY-SA 3.0
  - 가평: 0012-10-12 (2024-11-12) *Gapyeong - Chuncheon *Gyeonggi - Gangwon — Katsujiro Maekawa, CC0
  - 춘천: Chuncheon-01 — Mark Zastrow, CC BY 2.0
  - 강릉: Gyeongpo Beach 20220502 023 — Mobius6, CC BY-SA 4.0
  - 속초: Sokcho Beach 20221209 015 — Mobius6, CC BY-SA 4.0
  - 대전: Expo Bridge in Daejeon — Bernard Gagnon, CC0
  - 청주: Cheongju Sangdangsangseong — Hutch1225, Public domain
  - 천안: Independence Hall of Korea 01 — Lawinc82, CC BY-SA 3.0
  - 태안: 꽃지의석양 — HiHoHo, CC BY-SA 3.0
  - 광주: Gwangju Mudeungsan — Kgw1226, CC BY-SA 4.0
  - 전주: Jeonju Hanok Maeul 02 — Bernard Gagnon, CC0
  - 여수: Yeosu Odongdo 20180929 001 — Mobius6, CC BY-SA 4.0
  - 목포: Tafoni and Sandstone, Gatbawi Mokpo South Korea 07 — Korea Tourism Organization, KOGL Type 1
  - 부산: Gwangalli Beach and Gwangan Bridge Busan — Masterhatch, CC BY-SA 4.0
  - 대구: Seokguram at Palgong Mountain, Daegu — Ken Eckert, CC BY-SA 4.0
  - 울산: Daewangam Park — Shinfull, CC BY-SA 4.0
  - 경주: Cheomseongdae Observatory under blue sky in Gyeongju South Korea — Basile Morin, CC BY-SA 4.0
  - 안동: Hahoe Folk Village 03 — Bernard Gagnon, CC0
  - 제주: Yongduam in jeju — Jeong seolah, CC0
  - 서귀포: Jeongbang loin de la mer — SpaceFox, CC BY 4.0
- **날씨·기상특보**: 기상청 단기예보·기상특보 조회서비스 (공공데이터포털)
- **대기질**: 한국환경공단 에어코리아 대기오염정보 (공공데이터포털)
- **장소 검색**: 네이버 지역 검색 API (NAVER API HUB, 한 번에 최대 5건)
- **지도·길찾기**: 네이버 클라우드 플랫폼 Maps (Dynamic Map, Directions), SK open API Tmap (보행자 경로)
