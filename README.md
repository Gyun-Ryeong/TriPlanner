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
├── 스토리보드/      # 화면 설계 목업 이미지
└── README.md
```

## 현재 진행 상태

### 구현 완료
- **회원/인증**: 회원가입(필수·선택 약관 동의 포함)/로그인(JWT), 프로필 수정(이름·전화번호·비밀번호 변경), 여행 알림 켜기/끄기. 네이버 로그인 코드는 있으나 실제 로그인 흐름은 아직 검증되지 않았습니다.
- **여행 일정**: 지역(지도에서 선택) · 날짜로 여행 생성, 일차별 일정 입력 전용 화면과 조회 화면 분리, 장소 검색(한국관광공사 TourAPI)·메모 추가/삭제, 여행 삭제.
- **지도/길찾기**: 네이버 지도에 장소 마커와 동선 표시, 하루 동선의 자동차 길찾기(네이버 Directions).
- **실시간 알림**: 권역(서울/경기·인천/강원/충청/전라/경상/제주)별 날씨(기상청 단기예보, 기온 범위 + 가장 주의할 도시, '도시별 보기'로 부산·대구 등 도시별 확인), 기상특보 현황, 권역별 대기질 현황(에어코리아, 시도별 값 펼쳐 보기). 여행 시작이 3일 이내이면 날씨·대기질 예보·기상특보로 **주의/참고** 알림을 만들어 헤더 종 아이콘, Home, 알림 탭, 일정 화면에 보여줍니다. (예보는 여행일 기준 3일 이내만 제공)
- **공통 화면**: 로그인 상태에 따른 라우트 보호, 플로팅 챗봇 위젯(대화 기능은 준비 중).

### 구현 전 / 준비 중
- **AI 여행 챗봇(RAG)**: 백엔드 연동 전이라 안내 문구만 있습니다.
- **알림 발송**: 문자·이메일 등 외부 발송은 없고 앱 안 알림만 제공합니다. (프로필의 '일정 변경 및 준비 알림', '마케팅 정보 수신' 토글은 비활성)
- 체크리스트, 3일을 넘는 날짜의 예보(기상청 중기예보 미연동) 등.

## 데이터 출처

- **대한민국 시도 경계 지도 데이터** (`frontend/public/korea-provinces.json`): 통계청 통계지리정보서비스(SGIS)가 공개한 자료를 [southkorea/southkorea-maps](https://github.com/southkorea/southkorea-maps) 저장소가 정리해 배포한 것을 사용했습니다. [공공누리 제1유형](http://www.kogl.or.kr/info/license.do) 라이선스.
- **날씨·기상특보**: 기상청 단기예보·기상특보 조회서비스 (공공데이터포털)
- **대기질**: 한국환경공단 에어코리아 대기오염정보 (공공데이터포털)
- **장소 검색**: 한국관광공사 TourAPI (공공데이터포털)
- **지도·길찾기**: 네이버 클라우드 플랫폼 Maps (Dynamic Map, Directions)

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
```

- `notify_trip_alerts`: 프로필에서 켜고 끄는 여행 알림 설정 (기본값 켜짐)
- `consent_at`: 필수 약관(이용약관, 개인정보 수집·이용) 동의 시각 — 회원가입 화면을 거치지 않은 계정은 `NULL`
- `consent_third_party`, `consent_marketing`: 선택 동의 여부

> 회원가입 화면의 약관 본문은 개발용 임시 문구입니다. 정식 서비스 전에 검토된 약관으로 교체해야 합니다.
