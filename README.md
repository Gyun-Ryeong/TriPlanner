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
- **축제 달력**: 전국 축제를 월별 달력으로 보고, 공휴일도 함께 표시
- **여행 공유**: 내 일정을 읽기 전용 링크로 공유
- **내 여행 관리**: 프로필, 여행 목록·통계, 다가오는 여행의 알림 확인

## 기술 스택

| 영역 | 기술 |
| --- | --- |
| Frontend | React 19, Vite, React Router |
| Backend | Java 25, Spring Boot 4.1 (Maven, Spring Data JPA, Spring Security + JWT) |
| AI 챗봇 | Python, FastAPI, Ollama (로컬 LLM), MariaDB 벡터 검색 |
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

## 실행 방법

| 구성 요소 | 폴더 | 명령 | 주소 |
| --- | --- | --- | --- |
| DB | - | MariaDB 실행 (DB `triplanner`) | 3308 |
| AI 모델 | - | Ollama 실행 (`ollama serve`, 모델 예: `gemma4:e4b`) | 11434 |
| AI 챗봇 서버 | `rag_project` | `.venv\Scripts\activate.bat` → `python -m uvicorn api_server:app --port 8000` | 8000 |
| 백엔드 | `backend` | `mvnw spring-boot:run` | 8080 |
| 프론트엔드 | `frontend` | `npm install` → `npm run dev` | 5173 |

- 순서: DB → Ollama → 챗봇 서버 → 백엔드 → 프론트엔드
- **코드를 바꾼 뒤에는 챗봇 서버와 백엔드를 다시 켜야 반영됩니다.** 프론트엔드는 개발 서버가 자동으로 반영합니다.
- API 키는 `rag_project/.env`, `backend/src/main/resources/application-local.yml`에 넣고 **깃에 올리지 않습니다.**
- 챗봇의 장소 벡터 DB는 처음 한 번 `python build_vector_db.py`로 채웁니다 ([`rag_project/README.md`](rag_project/README.md#4-장소-벡터-db-mariadb)).

## 구현된 기능

- **회원/인증**: 회원가입(필수·선택 약관 동의 포함)/로그인(JWT), 프로필 수정(닉네임·전화번호·비밀번호 변경), 여행 알림·일정 변경 및 준비 알림 켜기/끄기, 마케팅 정보 수신 동의 철회. 회원 탈퇴(비밀번호와 확인 문구 입력)는 14일간 보관한 뒤 회원과 관련 데이터를 파기하며, 그 전에는 관리자가 복구할 수 있습니다.
- **여행 일정**: 지역(지도나 오른쪽 목록에서 도 단위로 선택, 아래 드롭다운에서 세부 지역(시)까지 선택 가능)·날짜로 여행 생성(시작일을 고르면 종료일이 그보다 빠를 때 자동으로 맞춰지고, 생성 후 뒤로가기를 눌러도 생성 폼으로 돌아오지 않음), 일차별 일정 입력 화면과 조회 화면 분리, 장소 검색(네이버 지역 검색)·메모 추가/삭제, 여행 삭제. 일정 수정 중에는 마지막 일차를 하나씩 추가·삭제해 여행 일수를 늘이거나 줄일 수 있고(최대 31일), 일정이 들어 있는 일차를 지울 때는 한 번 더 확인합니다. 여행 목록(여행 일정 탭)에는 지역 대표 사진이 함께 표시됩니다.
- **지도/길찾기**: 네이버 지도에 장소 마커와 동선 표시, 하루 동선의 자동차(네이버 Directions) / 도보(Tmap 보행자 경로, 장소 사이 구간별 호출) 길찾기. 도보는 거리가 너무 멀어 걸을 수 없는 구간이 있어도 전체가 실패하지 않고, 가능한 구간만 경로·합계에 넣고 해당 구간에는 '도보 경로를 추천드리기 어렵다'는 안내(다른 지도 서비스나 자동차 경로 이용 권유)를 보여줍니다.
- **실시간 알림**: 알림 탭은 내가 여행 가는 지역(예정·진행 중인 여행의 지역)의 날씨·대기질·기상특보를 작은 카드로 가장 먼저 보여주고(세부 지역을 고른 여행은 그 도시 기준 날씨), '전체 지역 날씨·대기질·특보 보기' 버튼을 누르면 다른 지역도 펼쳐 볼 수 있습니다(예정된 여행이 없으면 처음부터 전체 지역을 보여줍니다). 권역(서울/경기·인천/강원/충청/전라/경상/제주)별 날씨(기상청 단기예보, 기온 범위 + 가장 주의할 도시, '도시별 보기'로 도시별 확인), 기상특보 현황, 권역별 대기질 현황(에어코리아, 시도별 값 펼쳐 보기). 여행 시작이 3일 이내이면 날씨·대기질 예보·기상특보로 **주의/참고** 알림을 만들어 헤더 종 아이콘, Home, 알림 탭, 일정 화면에 보여줍니다. (예보는 여행일 기준 3일 이내만 제공)
- **출발 전 체크리스트**: 여행을 처음 열 때 기간(당일/숙박)·지역(제주 항공·렌터카)·출발 계절에 맞는 준비 항목이 D-7(예약)·D-3(확인)·D-1(짐)·출발 당일 기한으로 자동 생성됩니다. Home 카드에서 진행률과 지금 챙길 항목을 체크하고, `/trips/:id/checklist` 에서 전체 보기·직접 추가·삭제를 합니다. 이미 기한이 지난 항목은 만들거나 보여주지 않습니다. Home·마이페이지의 '다가오는 여행'은 종료일이 오늘 이후인 가장 빠른 여행입니다.
- **축제 달력**(`/festivals`, 로그인 없이 볼 수 있음): 한국관광공사 TourAPI의 월별 축제를 시도별로 달력에 펼쳐 보여주고, 같은 날 겹치는 축제는 네이버 뉴스 건수가 많은 쪽을 대표로 세웁니다. 공휴일(한국천문연구원 특일 정보, 대체·임시공휴일 포함)을 함께 표시합니다.
- **여행지 소식**: 여행 일정 화면(칸마다 6장)과 알림 탭(다가오는 여행 2개, 칸마다 4장)에 그 여행지 소식을 사진 카드로 보여줍니다. **지역 소식** 탭(축제·관광 소식 먼저)과 **사건사고** 탭(통제·침수·특보 같은 여행 영향 이슈를 '주의'로 먼저, 그다음 화재·교통사고·사건)으로 나눠 보고, 주의 이슈가 있으면 사건사고 탭에 표시됩니다. 사진은 기사 원문의 대표 사진(미리보기)이고, 없으면 지역 대표 사진입니다. 네이버 뉴스와 연합뉴스 재난·사건사고 기사(행정안전부 공유플랫폼)를 쓰며, 같은 지역은 15분 동안 다시 모으지 않습니다.
- **여행 공유**: 일정 화면에서 공유를 켜면 읽기 전용 링크(`/shared/:code`)가 만들어지고, 로그인하지 않은 사람도 일정과 지도를 볼 수 있습니다. 공유를 끄면 링크가 바로 막힙니다.
- **일정 변경·준비 알림**: 아직 출발하지 않은 여행에 대해 체크리스트에서 오늘까지인 미완료 항목, 출발 7일 이내인데 비어 있는 일차를 알려줍니다. 요청 때마다 계산하며 헤더 종·Home·알림 탭에 여행 위험 알림과 함께 표시됩니다. 앱 안 알림만 제공합니다.
- **AI 여행 챗봇(RAG)**: 챗봇 페이지와 플로팅 위젯에서 대화로 일정·맛집·숙소·축제·지역 소식을 받습니다. 새 대화는 환영 화면과 예시 질문으로 시작하고, AI 답변은 말풍선 없이 봇 아이콘 옆에 보여주며(답변 복사 버튼), 답변을 기다리는 동안 점 애니메이션과 경과 시간을 표시합니다. 입력창은 여러 줄을 치면 높이가 늘어납니다. 페이지와 위젯은 같은 대화를 이어갑니다. 대화는 목록(페이지는 왼쪽, 위젯은 '대화 목록' 화면)으로 보관되며 이 브라우저(localStorage)에만 저장됩니다. 📌로 고정하지 않은 대화는 만든 지 24시간 뒤 사라지고(전체 10개, 고정 최대 5개), 제목은 첫 질문으로 정해지며 ✏️로 바꿀 수 있고, 목록에서 제목이 길어 잘려도 마우스를 올리면 전체 제목이 보입니다. 챗봇이 만든 일정은 '내 여행에 저장' 버튼으로 내 여행에 저장되고(장소·시간·메모 포함), 일정 화면의 '일정 수정'에서 시간·메모 수정, 순서 변경, 추가·삭제를 할 수 있습니다. 자세한 기능은 [`rag_project/README.md`](rag_project/README.md) 참고.
  - **답변 기다리는 동안**: "날씨를 모으고 있어요 → AI가 일정을 짜고 있어요 (2/3)"처럼 지금 하는 일을 1.5초마다 보여주고, '보내기 취소'를 누르면 챗봇의 대화 기억도 그 말을 보내기 전으로 되돌립니다(처리 중이면 AI 호출 전에 멈춤).
  - **일정 품질**: 하루 장소를 이동거리가 가장 짧은 순서로 잇고 날짜 사이 장소를 맞바꿔 가까운 곳끼리 모읍니다(하루 이동 44~60% 감소). 휴무일인 장소는 다른 날로 옮기거나 바꾸고, 장소마다 운영시간을 보여줍니다.
  - **장소 검색**: 전국 47,703곳을 미리 저장한 벡터 DB(MariaDB `tour_place`, 백엔드와 같은 DB)에서 찾고, AI 유사도 검색에 키워드 검색을 섞어(하이브리드) "국밥", "해수욕장" 같은 정확한 말도 잡습니다(질문 30개 기준 정확도 P@5 0.37 → 0.91).
  - **취향 기억**: 이번에 취향을 말하지 않으면 '내 여행'에 저장한 장소로 자주 가는 종류(박물관·카페 등)를 반영하고, 저장했던 곳보다 새로운 곳을 먼저 보여줍니다.
  - **대충 쓴 말 이해**: 낼·담주·금욜·월~금·다음달 5일·12월 초·크리스마스·다다음주·저번주 같은 표현을 날짜로 읽고, "다음달"만 말하면 며칠인지 되묻습니다.
- **관리자 페이지**(`/admin`, 관리자 계정만): 챗봇 서버 상태, 챗봇 개발자 모드(응답 속도·일정 품질 지표 표시), 회원 목록과 탈퇴 회원 복구, 챗봇 호출 오류 기록(30일 보관).
- **공통 화면**: 로그인 상태에 따른 라우트 보호, 플로팅 챗봇 위젯. 색은 파란색 계열을 기본으로 하고, 빨강(오류·삭제·경보)과 주황(주의·위험 알림)은 정말 강조할 때만 씁니다. 여행 알림의 '참고' 줄은 흰 배경에 배지만 색을 넣고, 알림 문구의 날짜를 굵게 보여줍니다.

## 알려진 한계

- **네이버 로그인**: 코드는 있으나 실제 로그인 흐름은 아직 검증되지 않았습니다. 카카오·구글 버튼은 화면만 있습니다. 네이버로 가입한 회원은 비밀번호가 없어 지금은 회원 탈퇴를 할 수 없습니다.
- **알림 발송**: 문자·이메일 등 외부 발송은 없고 앱 안 알림만 제공합니다.
- **예보 기간**: 3일을 넘는 날짜의 예보(기상청 중기예보)는 연동하지 않았습니다.
- **챗봇 대화 기억**: 챗봇 서버 메모리에만 있어서 서버를 다시 켜면 이어지던 대화의 조건이 사라집니다(화면의 대화 목록은 브라우저에 남음).
- **장소 소개글**: TourAPI 하루 호출 한도 때문에 장소 소개글은 일부만 받아 두었습니다. `build_vector_db.py --overview`로 나눠서 채웁니다.

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
- **축제 정보·공휴일**: 한국관광공사 TourAPI(국문 관광정보 서비스), 한국천문연구원 특일 정보 (공공데이터포털)
- **축제 관련 뉴스**: 네이버 검색 API (뉴스)
- **장소 검색**: 네이버 지역 검색 API (NAVER API HUB, 한 번에 최대 5건)
- **지도·길찾기**: 네이버 클라우드 플랫폼 Maps (Dynamic Map, Directions), SK open API Tmap (보행자 경로)
