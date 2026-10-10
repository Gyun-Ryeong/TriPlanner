# TriPlanner

국내 여행의 모든 순간을 더 안전하고 자유롭게 — 맞춤 일정, 실시간 여행 알림, AI 여행 챗봇을 제공하는 국내 여행 플래너 서비스입니다.

## 팀원

- 이동희
- 김령균
- 이시우

## 주요 기능 (기획 기준)

- **여행 일정 관리**: 지역 선택 후 동선/일정 생성 및 수정
- **AI 여행 챗봇**: 최신 여행 정보 기반으로 일정·맛집 등을 추천 (RAG 기반)
- **실시간 여행 알림**: 여행 3일 전부터 여행지의 날씨·대기질(미세먼지)·기상특보를 확인해 주의/참고 알림 제공 (기상청·에어코리아 기반)
- **내 여행 관리**: 프로필, 여행 목록·통계, 다가오는 여행의 알림 확인

## 기술 스택

| 영역 | 기술 |
| --- | --- |
| Frontend | React (Vite), React Router |
| Backend | Java 25, Spring Boot 4.1.1 (Maven, Spring Data JPA, Spring Security + JWT) |
| Database | MariaDB (HeidiSQL로 관리) |
| 형상관리 | Git / GitHub |

## 폴더 구조

```
TriPlanner/
├── frontend/       # React 프론트엔드
├── backend/        # Spring Boot 백엔드
├── rag_project/    # AI 여행 챗봇 (Python, FastAPI + Ollama)
├── 스토리보드/      # 화면 설계 목업 이미지
└── README.md
```

## 현재 진행 상태

### 구현 완료
- **회원/인증**: 회원가입(필수·선택 약관 동의 포함)/로그인(JWT), 프로필 수정(이름·전화번호·비밀번호 변경), 여행 알림 켜기/끄기. 네이버 로그인 코드는 있으나 실제 로그인 흐름은 아직 검증되지 않았습니다.
- **여행 일정**: 지역(지도에서 선택) · 날짜로 여행 생성, 일차별 일정 입력 전용 화면과 조회 화면 분리, 장소 검색(네이버 지역 검색)·메모 추가/삭제, 여행 삭제.
- **지도/길찾기**: 네이버 지도에 장소 마커와 동선 표시, 하루 동선의 자동차 길찾기(네이버 Directions).
- **실시간 알림**: 권역(서울/경기·인천/강원/충청/전라/경상/제주)별 날씨(기상청 단기예보, 기온 범위 + 가장 주의할 도시, '도시별 보기'로 부산·대구 등 도시별 확인), 기상특보 현황, 권역별 대기질 현황(에어코리아, 시도별 값 펼쳐 보기). 여행 시작이 3일 이내이면 날씨·대기질 예보·기상특보로 **주의/참고** 알림을 만들어 헤더 종 아이콘, Home, 알림 탭, 일정 화면에 보여줍니다. (예보는 여행일 기준 3일 이내만 제공)
- **공통 화면**: 로그인 상태에 따른 라우트 보호, 플로팅 챗봇 위젯.
- **AI 여행 챗봇(RAG)**: 챗봇 페이지와 플로팅 위젯에서 대화로 일정·맛집·숙소·축제·지역 소식을 받습니다. 프론트 → 백엔드 `/api/chat`(로그인 필요) → `rag_project` FastAPI 서버 순으로 전달되며, 페이지와 위젯은 같은 대화를 이어갑니다. 챗봇이 만든 일정은 '내 여행에 저장' 버튼으로 내 여행에 저장되고(장소·시간·메모 포함), 일정 화면의 '일정 수정'에서 시간·메모 수정, 순서 변경, 추가·삭제를 할 수 있습니다. 자세한 기능은 [`rag_project/README.md`](rag_project/README.md) 참고.

### 구현 전 / 준비 중
- **알림 발송**: 문자·이메일 등 외부 발송은 없고 앱 안 알림만 제공합니다. (프로필의 '일정 변경 및 준비 알림', '마케팅 정보 수신' 토글은 비활성)
- 체크리스트, 3일을 넘는 날짜의 예보(기상청 중기예보 미연동) 등.

## 데이터 출처

- **대한민국 시도 경계 지도 데이터** (`frontend/public/korea-provinces.json`): 통계청 통계지리정보서비스(SGIS)가 공개한 자료를 [southkorea/southkorea-maps](https://github.com/southkorea/southkorea-maps) 저장소가 정리해 배포한 것을 사용했습니다. [공공누리 제1유형](http://www.kogl.or.kr/info/license.do) 라이선스.
- **날씨·기상특보**: 기상청 단기예보·기상특보 조회서비스 (공공데이터포털)
- **대기질**: 한국환경공단 에어코리아 대기오염정보 (공공데이터포털)
- **장소 검색**: 네이버 지역 검색 API (NAVER API HUB, `naver.app` 키 사용, 한 번에 최대 5건)
- **지도·길찾기**: 네이버 클라우드 플랫폼 Maps (Dynamic Map, Directions)

## 전체 실행 순서

챗봇까지 쓰려면 아래 세 서버를 각각 다른 터미널에서 띄웁니다. 챗봇을 쓰지 않으면 1번은 생략해도 됩니다 (챗봇 화면에만 연결 오류가 표시됨).

1. RAG 챗봇 서버 (8000): `rag_project` 폴더에서 `python -m uvicorn api_server:app --port 8000` — 설치와 키 설정은 [`rag_project/README.md`](rag_project/README.md) 참고, Ollama가 실행 중이어야 합니다.
2. 백엔드 (8080): 아래 "시작하기 (백엔드)" 참고. RAG 서버 주소를 바꾸려면 환경 변수 `RAG_BASE_URL` (기본 `http://localhost:8000`).
3. 프론트엔드 (5173): 아래 "시작하기 (프론트엔드)" 참고. 브라우저에서 `http://localhost:5173` 접속 → 로그인 → 여행 챗봇.

## 시작하기 (프론트엔드)

```bash
cd frontend
npm install
npm run dev
```

기본적으로 `http://localhost:5173` 에서 실행됩니다.

프로덕션 빌드:

```bash
npm run build
```

## 시작하기 (백엔드)

1. 로컬 MariaDB를 실행하고, `triplanner` 데이터베이스를 준비합니다.
2. `backend/src/main/resources/application-local.yml.example` 을 참고해서 **본인 로컬 DB 계정 정보와 API 키**로 `application-local.yml`(같은 폴더, 이미 생성되어 있고 gitignore 처리됨)을 채워주세요. 이 파일은 절대 Git에 올라가지 않습니다.
   - `public-data.service-key`: 공공데이터포털 키 (TourAPI, 기상청 단기예보·기상특보, 에어코리아 대기오염정보 활용신청 필요)
   - `naver.login.*`, `naver.map.*`: 네이버 로그인 / 네이버 클라우드 Maps 키
3. DB 스키마가 최신인지 확인합니다. (아래 "DB 스키마 변경 사항" 참고 — 컬럼이 없으면 백엔드가 기동되지 않습니다.)
4. 실행:

```bash
cd backend
./mvnw spring-boot:run
```

기본적으로 `http://localhost:8080` 에서 실행됩니다.

테스트 실행:

```bash
cd backend
./mvnw test
```

## DB 스키마 변경 사항

`spring.jpa.hibernate.ddl-auto=validate` 이므로 테이블은 직접 관리하며, 엔티티에 추가된 컬럼은 아래 SQL을 각자 로컬 DB에 실행해야 합니다. (이미 실행했다면 다시 실행하지 않아도 됩니다.)

```sql
-- user: 전화번호 (선택 입력)
ALTER TABLE `user` ADD COLUMN phone VARCHAR(20) NULL AFTER nickname;

-- user: 여행 알림 수신 여부, 회원가입 약관 동의 내역
ALTER TABLE `user`
  ADD COLUMN notify_trip_alerts TINYINT(1) NOT NULL DEFAULT 1,
  ADD COLUMN consent_at DATETIME NULL,
  ADD COLUMN consent_third_party TINYINT(1) NOT NULL DEFAULT 0,
  ADD COLUMN consent_marketing TINYINT(1) NOT NULL DEFAULT 0;

-- user: 회원 탈퇴 시각 (탈퇴 후 14일이 지나면 회원과 관련 데이터 파기)
ALTER TABLE `user` ADD COLUMN withdrawn_at DATETIME NULL AFTER consent_marketing;
```

- `notify_trip_alerts`: 프로필에서 켜고 끄는 여행 알림 설정 (기본값 켜짐)
- `consent_at`: 필수 약관(이용약관, 개인정보 수집·이용) 동의 시각 — 회원가입 화면을 거치지 않은 계정은 `NULL`
- `consent_third_party`: 제3자 제공 동의 — 회원가입 항목에서 삭제되어 새 가입자는 항상 `0` (기존 데이터 호환용으로 컬럼만 유지)
- `consent_marketing`: 마케팅 정보 수신 동의 여부
- `withdrawn_at`: 회원 탈퇴 시각 — 값이 있으면 로그인·API 사용이 막히고, 14일이 지나면 매시 정각에 회원·여행·일정·챗봇 기록을 파기 (관리자 페이지에서 그 전에 복구 가능)

> 회원가입 약관 문구의 정본은 루트의 `약관동의.md` 이며, 화면 문구는 `frontend/src/lib/consentTexts.js` 에서 관리합니다.
