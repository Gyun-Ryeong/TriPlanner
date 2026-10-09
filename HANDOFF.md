# TriPlanner 인수인계 (HANDOFF)

**갱신: 2026-10-09 (금) 오후** · 기준 커밋 `ab9af93` (main) + **미커밋 작업 다수**(아래 2번)

> 이 파일은 새 세션이 "지금 어디까지 됐고, 뭘 건드리면 안 되는지"를 바로 알 수 있게 쓴 문서입니다.
> 작성 규칙: **확인한 사실**은 그대로, **추측·못 본 것**은 `(미확인)`으로 표시했습니다.
> 이전 기록(결정/실패)은 지우지 않고 옮겨 왔고, 무효가 된 것만 `(폐기됨: 이유)`로 표시했습니다.
> 이 저장소에는 원래 루트 `HANDOFF.md`가 없었습니다. 이전 세션들의 인수인계 기록과 프로젝트 메모에서 내용을 옮겨 이 파일을 새로 만들었습니다.

---

## 0. 작성 시점에 실제로 확인한 것

| 확인 | 결과 |
|---|---|
| `git log -10` | 최신 `ab9af93`(2026-10-06, ngrok 프록시) … `2e5d216`. 작성자 전부 `kimrg`. |
| `git status` | 수정 31개 파일 + 신규(untracked) 20개 파일(이 문서 제외). 브랜치 `main` 하나, 원격 `origin`(GitHub). push는 사용자가 직접 함. |
| `git diff --stat` | 추적 파일 31개 변경, +1304 / -188 (README 포함). 변경 내용 일부 직접 확인: `.gitignore`(+1줄), `TripController`(`GET /alerts` 추가), `common.css`(`.badge-info` 추가). |
| 백엔드 `./mvnw test` | **BUILD SUCCESS, 16개 통과** (`BackendApplicationTests` 1 + `TripAlertServiceTest` 15), 실패 0. 컨텍스트 로드 테스트는 로컬 DB(3307)가 켜져 있어야 통과. |
| 프론트 `npm run build` | **성공** (352 modules). |
| 프론트 `npm run lint` | 에러 0, **경고 5건**: `TripAlertsProvider.jsx:26`, `Home.jsx:43`, `TripSchedule.jsx:132`(set-state-in-effect), `TripSchedule.jsx:146`(exhaustive-deps: `trip`), `Toast.jsx:11`(렌더 중 ref 접근). |
| 사용자 서버 | 8080(백엔드), 5173(프론트) 실행 중. 8080 프로세스 시작 11:41 > 마지막 자바 수정 11:32 → **최신 코드 반영됨**(확인: `/api/weather`가 `cities`, `/api/air-quality`가 `areas` 반환, `/api/trips/alerts`·`PUT /api/me/notifications`는 무인증 시 401). |
| 로컬 DB `user` 테이블 | `phone`, `notify_trip_alerts`, `consent_at`, `consent_third_party`, `consent_marketing` 컬럼 있음. 테스트 계정(`tmp-%`) 0건. 현재 trip 3건, place 3건(사용자 데이터). |
| 자동 테스트 범위 | `TripAlertServiceTest`(알림 규칙)만 있음. 날씨/대기질 서비스, 컨트롤러, 프론트 테스트는 **없음**. |

---

## 1. 현재 상태

### 완료 — 커밋됨 (HEAD 이하)

| 항목 | 관련 파일 |
|---|---|
| 회원가입/로그인(JWT, BCrypt), 전역 예외 처리 | `backend/.../controller/AuthController.java`, `service/AuthService.java`, `security/*`, `common/GlobalExceptionHandler.java`, `frontend/src/pages/Login.jsx`, `Signup.jsx` |
| 라우트 보호 | `frontend/src/components/RequireAuth.jsx`, `frontend/src/App.jsx` |
| 네이버 소셜 로그인 **코드** (실제 동의 화면 왕복은 **미확인**) | `controller/NaverAuthController.java`, `service/NaverAuthService.java`, `frontend/src/pages/NaverCallback.jsx` |
| 여행/일정 CRUD (일차 자동 생성, 소유자 403, 날짜 축소 시 cascade) | `controller/TripController.java`, `service/TripService.java`, `domain/Trip*.java`, `frontend/src/api/trips.js` |
| 장소 검색(TourAPI 실시간) + 일정에 추가/삭제, 메모 항목 | `controller/PlaceController.java`, `service/PlaceService.java`, `frontend/src/api/places.js`, `pages/TripSchedule.jsx` |
| 네이버 지도 + 마커 + 자동차 길찾기(Directions 15) | `service/RouteService.java`, `dto/Route*.java`, `frontend/src/lib/naverMaps.js`, `pages/TripSchedule.jsx` |
| 프로필 수정(이름·전화·비밀번호), 전화 3-4-4 | `controller/ProfileController.java`, `service/ProfileService.java`, `common/PhoneNumbers.java`, `pages/ProfileEdit.jsx` |
| 여행 삭제(인라인 확인), 새 여행 제목 입력 렉 수정 | `components/TripDeleteButton.jsx`, `components/KoreaMap.jsx` |
| 기상특보 현황 `GET /api/weather/warnings` | `service/WeatherWarningService.java`, `controller/WeatherController.java` |
| 플로팅 챗봇 위젯(대화 기능 없음, 안내만) | `components/ChatbotWidget.jsx` |
| ngrok 지원(Vite가 `/api` 프록시, API 기준 경로 상대) | `frontend/vite.config.js`, `frontend/src/api/client.js` |

### 완료 — **미커밋** (동작·검증됨, 커밋만 안 됨)

| 항목 | 관련 파일 |
|---|---|
| 대기질 현재 측정 `GET /api/air-quality` → 이번에 **권역(7) + 시도별 `areas`** 구조로 개편 | `service/AirQualityService.java`, `controller/AirQualityController.java`, `dto/RegionAirQualityResponse.java`, `frontend/src/pages/Alerts.jsx/.css` |
| 권역별 날씨 `GET /api/weather` → **권역 7개 × 도시 22곳**(`cities`) 개편, 10분 캐시·병렬 조회 | `service/WeatherService.java`, `dto/RegionWeatherResponse.java`, `frontend/src/api/weather.js`, `Alerts.jsx` |
| 여행 임박 알림(여행 3일 전부터 날씨·대기질 예보·기상특보 → "주의/참고") `GET /api/trips/alerts` | `service/TripAlertService.java`, `dto/TripAlertsResponse.java`, `dto/DailyForecast.java`, `dto/AirForecast.java`, `common/TtlCache.java`, `controller/TripController.java`, `src/test/.../TripAlertServiceTest.java` |
| 알림 UI: 헤더 종 아이콘, Home/알림 탭/일정 화면 배너 | `components/AlertBell.*`, `TripAlertList.*`, `TripAlertsProvider.jsx`, `lib/tripAlertsContext.js`, `MainLayout.*`, `pages/Home.*`, `pages/TripSchedule.jsx` |
| 알림 on/off 토글(즉시 저장) + 성공 시 **1.5초 토스트** | `controller/ProfileController.java`, `service/ProfileService.java`, `dto/NotificationSettingsRequest.java`, `dto/ProfileResponse.java`, `frontend/src/api/profile.js`, `pages/ProfileEdit.jsx/.css`, `components/Toast.jsx/.css` |
| 회원가입 약관 동의 블록(필수 2 + 선택 3), 필수 항목 빨간 `*`, 가입 후 로그인 화면 이동 | `pages/Signup.jsx`, `pages/Login.jsx`, `pages/auth-form.css`, `lib/consentTexts.js`, `frontend/src/api/auth.js`, `dto/SignupRequest.java`, `service/AuthService.java`, `domain/User.java` |
| 여행 만들기/수정 화면 분리(`/trips/:id/plan` vs `/schedule/:id`) | `App.jsx`, `pages/NewTrip.jsx`, `pages/TripSchedule.jsx/.css` |
| README 갱신(구현 현황·데이터 출처·**DB 스키마 변경 SQL**), `.gitignore`에 로컬 작업 폴더 규칙 1줄 | `README.md`, `.gitignore` |

### 진행중
없음. (마지막 작업은 "프로필 알림 토글 안내를 토스트로" 였고 끝까지 완료됨.)

### 미착수

| 항목 | 비고 |
|---|---|
| 여행에 **도시** 저장 → 알림을 그 도시 기준으로 | 사용자 결정 대기. DB `ALTER` + `NewTrip` UI 변경 필요(아래 6번) |
| 프로필 저장·비밀번호 변경 성공 문구도 토스트로 통일 | 사용자에게 질문만 해 둠, 답 없음 |
| 알림 탭 날씨/특보/대기질 자동 새로고침 | 지금은 탭 진입 시 1회 |
| SMS·이메일 발송 | 사용자가 "심화 개발 과정"으로 미룸 |
| 약관 문구를 검토된 정식 문구로 교체 | 지금은 화면에 "임시" 표시된 개발용 문구 |
| 프로필의 '일정 변경 및 준비 알림'·'마케팅 정보 수신' 토글 | 의도적으로 비활성(준비 중) |
| 계정 삭제, 일정 항목 순서 변경, 항목별 시간/메모 편집, 여행 제목·지역·날짜 수정 화면 | 없음 |
| 모바일(좁은 폭) 레이아웃 검증 | **(미확인)** — CSS `@media (max-width: 900px)`만 있음 |

### 막힘 (외부 요인)

| 항목 | 이유 |
|---|---|
| **AI 여행 챗봇(RAG)** | 팀원이 별도 개발 중인 백엔드 API가 없음. `pages/Chatbot.jsx`는 "구현 중" 안내만. 연동 후 `ChatbotWidget.jsx` 패널 안에 대화를 넣기로 함 |
| 알림 4~10일 앞 확장 | 기상청 **중기예보** 서비스가 공용 키로 미승인. data.go.kr에 별도 신청 필요(신청은 사용자가 직접) |
| 도시 단위 대기질 | 에어코리아 **측정소 목록/통계** API가 공용 키로 미승인(`SERVICE_KEY_IS_NOT_REGISTERED`). 그래서 시도 단위까지만 |
| 지도 인증 실패 표시 | 네이버 클라우드 Maps 콘솔의 "Web 서비스 URL"에 등록되지 않은 출처(예: ngrok 도메인, 임시 포트)에서는 지도가 "인증 실패". 코드 문제 아님 |

---

## 2. 멈춘 지점

**마지막 작업:** 프로필의 "여행 알림 켜기/끄기" 성공 안내를 초록 인라인 글씨에서 **1.5초 토스트**로 교체 → 임시 서버 + 일회용 계정으로 확인(54ms 후 표시, 약 1.55초 후 사라짐, 연타 시 문구 갱신) → 로그 기록까지 완료. 그 뒤 이 인수인계 작성 요청을 받음.

**미커밋 변경 내용:** 위 "완료 — 미커밋" 표 전부. 여러 주제가 **같은 파일에 섞여 있음**:
- `WeatherService.java` — (a) 임박 알림용 일별 예보 요약 + (b) 권역×도시 병렬 조회
- `Alerts.jsx` — (a) 내 여행 알림 카드 + (b) 권역 날씨 카드/대기질 펼침
- `MainLayout.jsx`, `Home.jsx`, `TripSchedule.jsx`, `ProfileEdit.jsx` — 여러 기능이 겹침
- 신규 파일(untracked)은 `git add <경로>`로 하나씩 추가해야 함. **`git add -A` 금지**(루트의 ngrok 실행 파일 등이 섞이지 않게).

**DB:** 코드가 요구하는 컬럼은 모두 로컬 DB에 이미 있음(위 0번). 팀원 DB에는 README "DB 스키마 변경 사항"의 SQL을 실행해야 백엔드가 뜸(`ddl-auto=validate`).

---

## 3. 설계 결정과 이유

형식: **A 대신 B** — 이유 / 버린 대안.

### 제품·화면
- **네이버 지도를 쓴다, 카카오 대신** — 스토리보드는 카카오로 보이지만 사용자가 실제로는 네이버라고 확정(2026-09-27). 지도 키 값은 서버 설정에만 두고 클라이언트 ID만 `GET /api/config/naver-map-client-id`로 내려 줌.
- **Vite 사용, CRA 대신** — 사용자가 중간에 변경 요청. 다시 묻지 말 것. 스타일은 일반 CSS(Tailwind 등 금지).
- **상단 메뉴 5개 확정**(홈/여행 일정/여행 챗봇/내 여행/실시간 알림), 로고는 텍스트 "TriPlanner" — 스토리보드 초안끼리 불일치해서 사용자가 최종 확정.
- **여행 권역은 7개 "도" 단위** — 서울 특별시 / 경기도 · 인천 / 강원도 / 충청도 / 전라도 / 경상도 / 제주도. 지도 시도 17개가 이 7개로 묶임(`KoreaMap.jsx`의 `PROVINCE_TO_REGION`). 날씨·대기질 이름도 이 이름으로 통일(2026-10-09, 사용자 요청: "7개의 도 기준으로 이름을 경상도 강원도 등으로 교체하고, 상세 도시는 안에서 확인").
- **권역 날씨 카드 = 기온 범위 + 가장 주의할 도시 한 줄, 상세는 "도시별 보기"로 펼침** — 사용자 선택. 대안(대표 도시 1곳 값만 / 범위만 / 모달)은 사용자가 선택하지 않음. 카드의 "주의 줄" 규칙은 임의 결정: 비·눈·소나기 도시 우선, 없으면 강수확률 ≥ 50%(여행 알림 기준과 동일), 없으면 "강수 걱정 없어요".
- **"펼칠 때만 불러오기" 대신 한 번에 받아 화면에서 펼침** — 주의 줄을 만들려면 모든 도시 값이 필요해서. 대신 서버 캐시로 호출 부담을 줄임.
- **대기질 권역 값 = 소속 시도 중 가장 나쁜(높은) 값 + 그 시도 이름**, 평균 아님 — 시도별 규모가 달라 평균은 의미가 약함. 강원·제주·서울은 시도가 하나라 펼침 없음(사용자 확인: "그냥 그대로 두기", 설명 문구도 추가 안 함).
- **안전점수 취소, "여행 임박 알림"로 대체**(2026-10-08) — 한 달 뒤 여행의 점수는 의미 없고, 단기예보·에어코리아 예보가 약 3일치뿐. 알림은 앱 안(헤더 종 + 화면)만, 창은 오늘~+2일, 3일 넘는 여행은 안내 문구.
- **알림 이름: 강함 = "주의"(주황), 약함 = "참고"(파랑)** — 너무 겁주지 않으려고. API는 코드(`DANGER`/`CAUTION`)만 주고 화면 이름은 `frontend/src/lib/tripAlertsContext.js`에서만 정함(바꾸려면 여기 한 곳).
- **알림 임계값은 상수**(`TripAlertService` 상단) — 강수확률 ≥ 50%, 비/눈 있음 = 참고; 시간당 30mm / 눈 5cm = 주의; 최고기온 33/35, 최저 -10/-15; 미세먼지 "나쁨" = 참고, "매우나쁨" = 주의; 기상특보 주의보 = 참고, 경보 = 주의. 사용자가 위임한 값이라 바꿔도 됨. 오존은 마스크로 막을 수 없어 제외.
- **성공 안내는 토스트(1.5초), 실패는 빨간 인라인 글씨 유지** — 실패는 읽을 시간이 필요. 토스트는 `message.id`가 바뀔 때마다 타이머 재시작.
- **토글은 누르는 즉시 저장** — 저장 버튼을 따로 두지 않음.
- **프로필 이메일은 수정 불가** — JWT에 이메일이 들어 있고 로그인 계정이라서.
- **가입 후 자동 로그인 대신 로그인 화면으로 이동** — 사용자 요청(2026-10-07).
- **약관: 필수 2(이용약관·개인정보) + 선택 3(여행 알림·제3자 제공·마케팅)**, 알림 수신 미동의 시 알림 OFF로 시작. 약관 문구는 **임시**(출시 전 교체 필수).
- **같은 날 같은 장소 중복 허용**("n번째 방문" 표시) — 사용자 결정.
- **장소 검색은 TourAPI 실시간 호출, DB 선적재 대신** — 응답 0.26~0.39초로 측정, 갱신 주기 문서가 없어 선적재 이득이 불확실.
- **길찾기는 자동차만**(Directions 15) — 네이버에 도보/대중교통 API 없음. 기본 최적 경로만, 정차점 최대 17개.
- **네이버 소셜 로그인은 이메일로 find-or-create**, `provider/social_id` 컬럼 추가 대신 — DB를 사용자가 수작업으로 관리해서 마이그레이션을 피함. 네이버로 만든 계정은 무작위 비밀번호(비밀번호 변경 불가).
- **날씨 카드 값은 "가장 가까운 예보 슬롯"(발표 직후 1시간 뒤)** — 사용자가 "강수확률(다음 1시간 기준)" 라벨로 유지하기로 함. 발표 사이에는 최대 3시간 전 시각 값이 보임.

### 기술
- **JPA(Hibernate) 사용, JDBC/MyBatis 대신** — CRUD 중심 도메인. **인증은 Spring Security + JWT**(무상태). Maven, Java 25, Spring Boot 4.1.1(→ Jackson 3: `tools.jackson.databind`).
- **`ddl-auto=validate`** — 스키마는 사람이 직접 관리. 엔티티에 컬럼을 추가하면 ALTER SQL을 README에 기록해야 함.
- **브랜치는 `main` 하나** — 예전 `backend`/`frontend` 장기 브랜치가 서로의 폴더를 지워 혼란 → 2026-09-28 통합.
- **프론트가 `/api`를 Vite 프록시로 보냄(상대 경로), 직접 `localhost:8080` 호출 대신** — ngrok 같은 외부 접속 시 브라우저의 localhost가 달라지는 문제. 프록시에서 `origin` 헤더를 제거해 백엔드 CORS 거절을 피함. `allowedHosts`는 사용자가 쓰는 ngrok 도메인 1개만.
- **외부 API 호출은 캐시 + 병렬 + 타임아웃** — 날씨(권역) 10분, 날씨(일별 예보) 10분, 대기질(현재) 5분, 대기질 예보 30분, 특보(알림용) 5분. 모두 서버 메모리라 재시작 시 사라짐. **일부 실패한 결과는 캐시하지 않음**(`TtlCache.getIfPresent/put`). 읽기 타임아웃 8초, 대기질은 실패 시 1회 재시도.
- **권역 → 도시 격자는 기상청 공식 변환식으로 계산** — 위경도를 변환해 기존 검증된 대표 도시 7곳과 비교, 6곳 일치(제주만 1칸 차이 → 기존 `52,38` 유지, 서귀포는 `52,33`). 오차는 격자 1칸(약 5km). 도시 선정(22곳)은 임의 결정.
- **각 권역의 첫 도시 = 대표 도시** — 여행 알림의 일별 예보가 이 도시 기준이라 `WeatherService.REGIONS`의 **도시 순서를 바꾸면 알림이 바뀜**.
- **테스트 데이터는 일회용 계정(`tmp-*@test.local`)으로, 끝나면 DB에서 삭제**. 토큰을 파일로 저장하지 않고 브라우저 안에서 가입·로그인해 해당 출처 localStorage에만 넣음.

---

## 4. 시도했다 실패한 것

| 시도 | 실패 원인 / 에러 | 다시 시도하지 말아야 하는 이유 |
|---|---|---|
| `react-simple-maps`로 한국 지도 | React 19와 peer dependency 충돌로 설치 실패(정확한 에러 문구는 기록 없음) | React ≤ 18만 지원. 대신 `@vnedyalk0v/react19-simple-maps` 사용 중 |
| 위 라이브러리에 지도 URL 문자열 전달 | `Strict HTTPS-only mode` — `http://localhost`에서 거부 | `KoreaMap.jsx`는 `fetch`로 받은 **파싱된 객체**를 `geography`에 넘김. "URL로 단순화"하면 조용히 깨짐 |
| 지도 투영 `scale 5500, height 560` | 본토는 보이나 제주가 SVG 밖으로 잘림 | 현재 `center [127.8,36], scale 5000, 500×650`. 지도 비율·권역을 바꾸면 **제주부터** 확인 |
| 공용 키로 에어코리아·기상특보 | 당시 `SERVICE_KEY_IS_NOT_REGISTERED_ERROR` | **(폐기됨: 2026-10-05/07에 승인되어 현재 동작)** 단, 측정소 목록(`MsrstnInfoInqireSvc`)·통계(`ArpltnStatsSvc`)는 지금도 미승인 |
| 기상청 중기예보로 4~10일 알림 | 공용 키 미승인 | 별도 신청 전에는 불가 |
| `getWthrWrnList`(특보 발표 이력)로 30일 조회 | `resultCode=99`, "최대 조회 기간은 오늘 기준으로 6일 전까지입니다." | 6일 이내로만 조회 가능. 이력 목록에는 "해제" 발표도 섞임. 현재 기능은 `getPwnStatus`(현재 발효 목록)만 사용 |
| 대기질 17개 시도를 **동시에** 호출(타임아웃·재시도·캐시 정책 없이) | 최초 호출 30초, 서울·경기 누락 상태가 5분간 캐시됨. 시도별 순차 호출은 모두 정상이었고 서울만 한 번 16초 걸림(서울 지연은 확인, **경기 누락 원인은 (미확인)**) | 지금 코드는 타임아웃 8초 + 1회 재시도 + 부분 실패 캐시 안 함. 이 안전장치를 빼지 말 것 |
| 날씨 일별 요약을 `numOfRows` 작게 | 3일치가 900행 안팎 | `getVilageFcst`는 `numOfRows=1500` 필요 |
| 한 파일을 편집 호출 두 번으로 나눠 수정 | Vite가 반쯤 고친 모듈을 캐시 → 브라우저에 "X is not defined" (파일은 정상) | 파일을 `touch`해서 재변환. 가능하면 한 번에 수정 |
| Git Bash `curl -d`로 한글 전송 | 한글 깨짐 | ASCII 페이로드 또는 URL 인코딩, 브라우저 `fetch`는 정상 |
| PowerShell에서 `mysql -h127.0.0.1 ...` | 점에서 인자가 잘려 `mysql` 사용법만 출력 | `--host=127.0.0.1 --port=3307 --user=root` 형태로 쓰고, SQL은 표준입력(here-string)으로 전달 |
| PowerShell `Invoke-RestMethod`로 한글 JSON 읽기 | 출력이 깨져 보임(UTF-8을 다른 코드페이지로 해석) | `Invoke-WebRequest`의 `RawContentStream`을 UTF-8로 디코딩해서 `ConvertFrom-Json` |
| 테스트용 계정 토큰을 파일로 저장 | 자동 검토에서 차단(토큰/계정 데이터를 작업 범위 밖 경로에 저장) | 브라우저 안에서 가입·로그인 후 localStorage에 직접 주입 |
| 자동화 도구의 ref 클릭으로 React `onClick` 호출 | 일부 클릭이 React 핸들러에 전달되지 않음 | `element.click()`을 JS로 실행하거나 좌표 클릭 |
| 오래된/백그라운드 브라우저 탭 스크린샷 | 시간 초과 | 새 탭을 만들어 확인. 창 크기 조절은 실제 뷰포트를 바꾸지 못해 모바일 폭 검증 불가 |
| 모든 커밋에 공동 작성자/자동 생성 표기가 들어감 | 저장소에 도구 흔적이 남아 사용자가 원치 않음 | 히스토리를 한 번 재작성해 제거함. **커밋 메시지에 공동 작성자·자동 생성 문구를 절대 넣지 말 것** |
| 알림 UI의 안전 "점수" | 단기예보 범위(3일)와 맞지 않음 | **(폐기됨: 2026-10-08, 임박 알림으로 대체)** |
| 가입 시 차량 보유·중요도 설문(개인화) | 논의만 하고 보류. 차량 없는 사용자용 도보/대중교통 경로 API가 없음 | 먼저 도보/대중교통 데이터 출처가 필요 |

---

## 5. 알려진 버그 / 주의점 (재현 방법)

| # | 내용 | 재현 / 확인 방법 |
|---|---|---|
| 1 | **여행 알림이 도시를 모름** — 권역 대표 도시 기준. 대구 여행인데 부산 날씨로 알림이 나갈 수 있음 | 지역을 "경상도"로 여행을 만들고 날짜를 오늘~+2일로 설정 → `GET /api/trips/alerts`의 예보는 부산 격자 기준(`WeatherService.REGIONS`의 경상도 첫 도시) |
| 2 | 에어코리아 **서울 응답이 가끔 10초 이상** → 캐시가 비었을 때 알림 탭 대기질이 느림 | 서버 재시작 직후 `GET /api/air-quality` 첫 호출 시간 측정(관측: 8.7초, 직접 호출 16초). 그 뒤 5분은 수십 ms |
| 3 | 알림 탭의 날씨/특보/대기질 **자동 새로고침 없음** | 탭을 열어 둔 채 시간이 지나도 갱신 안 됨(새로고침/재진입 필요). 헤더 종 아이콘만 10분마다 갱신 |
| 4 | Home "다가오는 여행" = 시작일이 가장 이른 여행이라 **이미 지난 여행**일 수 있음 | 지난 여행만 있는 계정으로 Home 확인 → "이미 지난 여행이라 알림이 없어요" |
| 5 | 기상특보 지역 매칭이 **키워드 방식** — "광주"가 경기 광주와 헷갈릴 수 있고, 해상 특보는 매칭 안 됨 | `TripAlertService.WARNING_KEYWORDS` 확인 |
| 6 | 단일 도시 권역(서울)에서 비가 오면 카드의 하늘 상태와 주의 줄이 같은 말을 반복 | 비 예보일 때 서울 카드 확인(사소) |
| 7 | 전화번호 입력 중 **커서가 맨 뒤로 점프** | 프로필에서 중간 숫자를 지우거나 수정 |
| 8 | 비밀번호 변경해도 기존 JWT가 무효화되지 않음. 네이버로 가입한 계정은 비밀번호 변경 불가. 계정 삭제 없음 | — |
| 9 | 장소 저장 `POST /api/places`는 클라이언트가 보낸 이름·좌표를 길이/범위만 검증하고 TourAPI와 대조하지 않음 | — |
| 10 | 바다 건너는 경로(제주↔서울)가 비현실적인 약 520km 도로 경로로 나옴 — 방지 로직 없음 | 일정에 서울·제주 장소를 같은 날 넣고 길찾기 |
| 11 | 린트 경고 5건(0번 표) — 특히 `Toast.jsx:11`은 **렌더 중 `ref.current = onClose`** 대입. 동작은 정상이나 규칙 위반 | `npm run lint` → 효과(effect) 안에서 ref를 갱신하도록 고치면 됨 |
| 12 | 날씨 카드 부분 실패: 일부 도시가 실패하면 그 도시만 목록에서 빠지고 **캐시되지 않아** 다음 요청에서 재시도됨. 전부 실패하면 502 | 서비스 키를 틀리게 한 임시 서버로 확인 가능 |
| 13 | `TripSchedule`을 다른 `tripId`로 **리마운트 없이** 재사용하면 지도가 분리된 컨테이너에 묶일 수 있음 | **(미확인)** 재현 못 함. 지금 라우트는 리마운트됨 |
| 14 | 지도는 등록 안 된 출처(ngrok 등)에서 인증 실패. 코드는 `window.naver?.maps`를 확인해 화면이 하얗게 죽지는 않음 | 5173 외 출처에서 일정 화면 열기 |
| 15 | 날씨 카드의 기온·강수확률은 발표 사이에 **최대 3시간 전 슬롯 값** (설계 결정 3번 참고) | 14:20에 카드를 보면 14시 발표분의 15시 슬롯 값 |
| 16 | `GET /api/weather/warnings`는 캐시 없음(알림 탭 진입마다 기상청 호출). 여행 알림 쪽만 5분 캐시 | — |
| 17 | 모바일 폭 레이아웃 **(미확인)**. 알림 탭 날씨 카드는 772px 폭에서 2열만 확인 | — |

---

## 6. 다음 할 일 Top 5 (우선순위순)

### 1. 미커밋 작업을 주제별로 나눠 커밋 (사용자가 커밋을 요청했을 때만)

**어느 파일의 무엇을 어떻게:** 아래 6개 묶음으로 `git add <경로>`(파일 하나씩) → `git commit -m "<메시지>"`. **공동 작성자·자동 생성 문구 금지, push 금지.** 파일이 주제를 가로지르는 곳은 `git add -p`로 hunk를 골라야 함.

1. **가입·약관**: `frontend/src/pages/Signup.jsx`, `Login.jsx`, `auth-form.css`, `frontend/src/lib/consentTexts.js`, `frontend/src/lib/phoneFormat.js`, `frontend/src/api/auth.js`, `backend/.../dto/SignupRequest.java`, `service/AuthService.java`, `domain/User.java`
2. **프로필 알림 토글 + 토스트**: `controller/ProfileController.java`, `service/ProfileService.java`, `dto/ProfileResponse.java`, `dto/NotificationSettingsRequest.java`, `frontend/src/api/profile.js`, `pages/ProfileEdit.jsx`, `ProfileEdit.css`, `components/Toast.jsx`, `Toast.css`
3. **여행 임박 알림**: `service/TripAlertService.java`, `dto/TripAlertsResponse.java`, `dto/DailyForecast.java`, `dto/AirForecast.java`, `common/TtlCache.java`, `controller/TripController.java`, `src/test/.../service/TripAlertServiceTest.java`, `components/AlertBell.*`, `TripAlertList.*`, `TripAlertsProvider.jsx`, `lib/tripAlertsContext.js`, `frontend/src/api/trips.js`, `frontend/src/styles/common.css`, (`MainLayout.*`, `Home.*`, `TripSchedule.jsx`의 알림 hunk)
4. **알림 탭 권역 개편**: `service/WeatherService.java`, `service/AirQualityService.java`, `controller/AirQualityController.java`, `dto/RegionWeatherResponse.java`, `dto/RegionAirQualityResponse.java`, `frontend/src/api/weather.js`, `pages/Alerts.jsx`, `Alerts.css`
5. **생성/조회 화면 분리**: `App.jsx`, `pages/NewTrip.jsx`, `pages/TripSchedule.jsx`/`.css`의 해당 hunk
   (참고: `frontend/src/styles/common.css`의 변경은 `.badge-info`(알림 "참고" 파란 뱃지) 추가뿐이라 **3번 묶음**에 넣을 것)
6. **문서·설정**: `README.md`, `.gitignore`

주의: 3·4번은 `WeatherService.java`/`Alerts.jsx`를 함께 쓰므로 한 커밋으로 합치는 게 가장 안전. 각 커밋 직전에 `./mvnw -q test`와 `npm run build`를 돌릴 것.

### 2. 여행에 "도시" 저장 → 알림이 그 도시 기준으로 나가게 (먼저 사용자 확인 필요)
- `Trip` 엔티티(`backend/.../domain/Trip.java`)에 `city` 컬럼 추가 + `ALTER TABLE trip ADD COLUMN city VARCHAR(30) NULL` (README "DB 스키마 변경 사항"에도 추가).
- `frontend/src/pages/NewTrip.jsx`에서 권역 선택 뒤 도시 선택(`WeatherService.REGIONS`의 도시 목록과 동일하게, 백엔드가 목록 API로 내려주면 이중 관리 방지).
- `TripAlertService`가 `trip.getCity()`로 해당 도시의 격자·대기질 시도를 사용하도록 수정(도시가 없으면 현재처럼 대표 도시).

### 3. 알림 탭 자동 새로고침 + 성공 문구 토스트 통일
- `frontend/src/pages/Alerts.jsx`의 `useEffect`에 `setInterval`(날씨 10분, 대기질 5분은 서버 캐시와 맞춤) 추가.
- `ProfileEdit.jsx`의 "저장되었습니다."·"비밀번호가 변경되었습니다."도 `Toast`로(사용자 확인 후).
- `Toast.jsx:11`의 ref 대입을 `useEffect` 안으로 옮겨 린트 경고 제거.

### 4. 챗봇(RAG) 연동 — 팀원 API 확인 후
- 팀원 백엔드 엔드포인트가 있는지 먼저 물을 것. 있으면 `frontend/src/components/ChatbotWidget.jsx` 패널 안에 대화 UI, `pages/Chatbot.jsx`는 "크게 보기".
- 사용자가 구상한 후속: 알림이 뜨면 챗봇이 여행 일정을 읽고 실내 장소를 추천.

### 5. 출시 전 정리
- 약관 문구 교체(`frontend/src/lib/consentTexts.js`, 화면의 "임시" 표시 제거).
- 기상청 중기예보 사용 신청(4~10일 알림), 에어코리아 측정소 목록 신청(도시별 대기질) — 신청은 사용자가 data.go.kr에서 직접.
- 모바일 폭 점검, 날씨/대기질 서비스 단위 테스트 추가(지금 `TripAlertServiceTest`만 있음).

---

## 7. 새 세션이 건드리면 안 되는 것

**프로세스·환경**
- **사용자의 8080(백엔드)·5173(프론트)는 죽이거나 점유하지 말 것.** 검증용 서버는 다른 포트(예: 8081, 5174)에서 띄우고 끝나면 **내가 띄운 PID만** 종료. 백엔드 변경 후에는 사용자에게 재시작이 필요하다고 알림.
- `backend/src/main/resources/application-local.yml`(gitignore)에 DB·API 키가 있음. **값을 출력·복사·커밋·문서화하지 말 것**(키 이름은 `application-local.yml.example` 참고).
- 로컬 DB는 MariaDB `127.0.0.1:3307`, DB명 `triplanner`. 사용자 실제 계정은 `test@test.com`(userId 7)이며 trip 3건·place 3건이 사용자 데이터. 테스트 후 `tmp-%@test.local` 계정과 그 여행/장소만 지울 것.
- 브라우저 검증 시 사용자 실제 세션(localStorage `triplanner_auth`)을 건드리지 말 것. 일회용 계정을 임시 포트 출처에 주입.
- 루트의 ngrok 실행 파일·`start-ngrok.bat`은 `.gitignore` 대상. 사용자가 외부 공개에 씀. `vite.config.js`의 `allowedHosts`(ngrok 도메인 1개)와 `/api` 프록시의 `origin` 제거 설정을 지우지 말 것.

**Git**
- **push 금지**(사용자가 직접). `git add -A` 금지(파일을 하나씩). 커밋 메시지에 공동 작성자·자동 생성 문구·도구 이름을 넣지 말 것. 커밋은 사용자가 요청했을 때만.
- `.gitignore`의 난독화된 규칙(`.cur*r/`)을 풀어 쓰지 말 것. 저장소에 올라가는 파일에는 AI 도구 이름을 문자 그대로 쓰지 않음.

**코드 계약(바꾸면 다른 곳이 깨짐)**
- `ddl-auto=validate` 유지. 엔티티 컬럼을 늘리면 반드시 ALTER SQL을 README에 추가.
- **`trip.region`에 저장되는 문자열**(`NewTrip.jsx`의 권역 이름)은 `TripAlertService.REGION_IDS`(공백 제거 후 매칭)와 `TripSchedule.jsx`의 `REGION_CENTERS`가 그대로 사용. 이름을 바꾸면 알림·지도 중심이 조용히 깨짐. (날씨/대기질 화면 이름만 바꾸는 것은 안전.)
- `WeatherService.REGIONS`의 **각 권역 첫 도시 = 대표 도시**(여행 알림 기준). 순서 변경 금지.
- `GET /api/weather`는 `[ {regionId, regionName, cities:[…]} ]`, `GET /api/air-quality`는 `areas`·`Metric.area` 포함 구조. 프론트 `Alerts.jsx`가 의존.
- 알림 응답의 레벨은 코드(`DANGER`/`CAUTION`)이고 화면 이름은 `tripAlertsContext.js` 한 곳에서만 정의.
- `KoreaMap.jsx`의 `geography`는 **객체**(URL 문자열 금지), `React.memo` 유지(제거하면 제목 입력 렉 재발). 지도 데이터 출처 표기(통계청 SGIS, 공공누리 제1유형)는 README·`KoreaMap.jsx` 주석에 유지.
- 외부 API 호출의 **타임아웃·재시도·부분 실패 캐시 금지** 장치와 로그에 **예외 클래스 이름만** 남기는 방식을 유지(예외 메시지에는 서비스 키가 든 URL이 들어 있음).
- Spring Boot 4 → Jackson 3(`tools.jackson.databind.JsonNode`). `com.fasterxml` import 금지.
- 동의 문구(`consentTexts.js`)는 임시 문구임을 화면에 표시 중. 이 표시를 지우려면 문구 자체를 먼저 교체.

**임시·의도적 상태(고치지 말고 사용자에게 물을 것)**
- 챗봇은 "구현 중" 안내만(`Chatbot.jsx`, `ChatbotWidget.jsx`).
- 프로필의 '일정 변경 및 준비 알림'·'마케팅 정보 수신' 토글은 의도적으로 비활성.
- 같은 날 같은 장소 중복 허용, 알림 임계값 상수, 날씨 카드의 "다음 1시간 기준" 라벨은 사용자 결정.
- 네이버 소셜 로그인은 최하순위(건드리지 말고, 콜백 URL 설정 문제를 먼저 꺼내지도 말 것).

**작업 방식(프로젝트 규칙)**
- 설계·이름·구조 등 **선택이 필요한 지점은 임의로 정하지 말고 먼저 질문**. 큰 기능은 구현 → 실제 확인 → 경계 조건 점검 → 수정 → (요청 시) 커밋 순서.
- 재시작이 필요한 변경(백엔드 코드, `pom.xml`, `application*.yml`, `vite.config.js`, 새 의존성)은 끝에 반드시 알릴 것.
