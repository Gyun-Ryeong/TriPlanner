# TriPlanner - 대화형 여행 플래너 (RAG)

대화로 여행 정보를 모으고, **관광정보·날씨·미세먼지·최신 이슈 뉴스**를 반영해서 일자별 여행 일정을 짜주는 챗봇입니다.
일정이 나온 뒤에도 "2일차는 실내로 바꿔줘" 같은 말로 계속 수정할 수 있어요.

- LLM: **Ollama(로컬)** — 외부 유료 LLM API 없음
- 데이터: 한국관광공사 TourAPI 4.0, 기상청 단기예보, 에어코리아, 네이버 뉴스
- 화면: Streamlit 채팅 화면 / 연동: FastAPI 서버 (Spring Boot·React에서 호출)

---

## 목차

1. [빠른 시작](#빠른-시작)
2. [사용 가능한 기능](#사용-가능한-기능)
3. [실행 방법 (구성 요소별)](#실행-방법-구성-요소별)
4. [API 명세](#api-명세)
5. [환경 변수 (.env)](#환경-변수-env)
6. [문제 해결](#문제-해결)
7. [동작 원리](#동작-원리)
8. [폴더 구조](#폴더-구조)
9. [알아둘 점 / 한계](#알아둘-점--한계)

---

## 빠른 시작

> 모든 명령은 `rag_project` 폴더 안에서 실행합니다. (Windows 기준, macOS/Linux는 주석 참고)

```bash
# 0) 준비물: Python 3.10 이상(3.14에서 확인), Ollama (https://ollama.com)

# 1) 가상환경 + 패키지 설치
python -m venv .venv
.venv\Scripts\activate              # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

# 2) LLM 모델 받기 (PC 사양이 낮으면 gemma4:e4b 같은 작은 모델)
ollama pull gemma4:26b

# 3) .env 만들기 → 아래 "환경 변수" 표를 보고 키 입력
#    .env.example 이 있으면 복사:  copy .env.example .env   (macOS/Linux: cp)

# 4) 확인 후 실행
python -m unittest discover -s tests      # 키/Ollama 없이 로직 테스트
python diagnose_api.py                     # API 키 점검
python -m streamlit run chat_app.py        # 채팅 화면 → http://localhost:8501
```

---

## 사용 가능한 기능

채팅창(또는 `/chat` API)에 자연어로 말하면 요청 종류를 알아서 구분합니다.

| 기능 | 이렇게 말해보세요 | 결과 |
|---|---|---|
| 🗓 **여행 일정 만들기** | "이번 주말에 부산 2박 3일", "성남 7일 일정 짜줘" | 지역·출발일·기간을 대화로 모은 뒤(동행·취향은 한 번만 질문), 날씨·미세먼지를 반영한 **시간표형 일자별 일정** (장소·이동·점심/저녁 식당 포함) |
| ✏️ **일정 수정** | "2일차는 실내로 바꿔줘", "맛집도 넣어줘", "제주로 바꿔줘" | 이미 모은 데이터로 일정만 다시 구성 (외부 API 재호출 없음) |
| 🗺 **여러 지역 일정** | "대구 1박2일, 부산 2박3일 짜줘" | 지역별 독립 일정, 날짜는 순서대로 이어서 배정. "부산 2일차 바꿔줘"처럼 지역 지정 수정 |
| 📍 **여행지 추천** | "성남 여행지만 추천해줘", "실내 데이트 장소 알려줘" | 날짜 질문 없이 **테마별 목록** (자연·공원 / 문화·역사 / 쇼핑·실내 …) |
| 🍽 **맛집·카페** | "분당 맛집 알려줘", "판교 카페" | 3~5곳: 위치 · 대표 메뉴 · 영업시간·주차 |
| 🏨 **숙박 / 🎉 축제 / 🧭 추천 코스** | "성남 숙소 추천해줘", "부산 축제 알려줘", "성남 추천 여행코스" | 각각 3~5곳 목록 (체크인/아웃, 행사 기간, 코스 소요시간 등) |
| 🔎 **특정 장소 정보** | "모란시장 영업시간", "XX공원 어떤 곳이야?" | 그 장소 하나만: 주소 · 영업/관람 정보 · 특징 |
| 📰 **지역 소식(뉴스)** | "성남시 요즘 소식 있어?", "모란시장 관련 소식" | 지역 최근 2주 핵심 3~4개 / 특정 대상 관련 뉴스 1개 (AI 요약 없이 기사 그대로) |
| ⚠️ **리스크 알림용 조회** | `GET /risks?region=부산` | 특보·취소·통제 등 지역 이슈 뉴스만 (LLM 미사용, 빠름) |

- **전국 지원**: 시도뿐 아니라 전국 시·군·구(곡성, 영월, 울진 …)까지 인식합니다. 일상 단어와 겹치는 이름은 "고양시"처럼, 여러 시도에 있는 이름("고성")은 시도와 함께 말해 주세요.
- **날씨 반영**: 비/눈, 폭염·한파, 미세먼지 '나쁨'인 날은 자동으로 **실내 위주**로 짭니다.
- **AI가 실패해도 동작**: Ollama가 느리거나 꺼져 있어도 규칙 기반 기본 일정으로 답합니다.

---

## 실행 방법 (구성 요소별)

| 구성 요소 | 명령 | 주소 | 필요한 것 | 용도 |
|---|---|---|---|---|
| ★ **채팅 화면** | `python -m streamlit run chat_app.py` | http://localhost:8501 | 키 + Ollama | 대화형 여행 플래너 (메인) |
| ★ **API 서버** | `python -m uvicorn api_server:app --port 8000` | http://localhost:8000/docs | 키 + Ollama | Spring Boot / React 연동 |
| 단발 추천 화면 | `python -m streamlit run travel_app.py` | http://localhost:8501 | 키 + Ollama | 폼으로 조건 입력 → 추천 (이전 버전) |
| 범용 RAG 챗봇 | `python -m streamlit run app.py` | http://localhost:8501 | 키 + Ollama | 공공데이터+뉴스 Q&A (초기 실험용) |
| 오프라인 테스트 | `python -m unittest discover -s tests -v` | – | 없음 | 로직 검증 (네트워크·키 불필요) |
| API 키 진단 | `python diagnose_api.py [tour\|weather\|air\|naver\|ollama]` | – | 키 | 어느 API가 왜 실패하는지 원문 표시 |
| 단계별 점검 | `python check_setup.py [ollama\|apis\|vector\|e2e\|travel\|chat]` | – | 단계별 상이 | 연결 확인, `chat`은 실제 대화 1회 + 소요 시간 |

> Streamlit 화면을 두 개 동시에 띄우려면 포트를 바꾸세요: `python -m streamlit run travel_app.py --server.port 8502`

### 1) 채팅 화면 (Streamlit)

```bash
ollama serve                              # Ollama가 이미 실행 중이면 생략 (트레이 아이콘 확인)
python -m streamlit run chat_app.py
```

- 처음 실행 시 임베딩 모델(약 500MB)을 내려받아 1~2분 걸릴 수 있어요.
- `.env`는 시작할 때만 읽습니다. 값을 바꿨으면 `Ctrl+C` 후 다시 실행하세요.

### 2) API 서버 (FastAPI)

```bash
python -m uvicorn api_server:app --port 8000
# 개발 중 코드 자동 반영: --reload 추가
```

- http://localhost:8000/docs 에서 Swagger UI로 바로 호출해볼 수 있어요.
- CORS 허용: `http://localhost:3000`, `http://localhost:5173` (Vite). 다른 주소에서 호출하면 `api_server.py`의 `allow_origins`에 추가하세요.

### 3) 점검 순서 (처음 세팅하거나 안 될 때)

```bash
python -m unittest discover -s tests -v   # ① 코드 로직 (키/Ollama 불필요)
python diagnose_api.py                    # ② 키·API (어느 API가 왜 실패하는지)
python check_setup.py ollama              # ③ Ollama 연결
python check_setup.py chat                # ④ 대화형 플래너 전체 (실제 API + Ollama, 단계별 소요 시간)
```

---

## API 명세

| 메서드 | 경로 | 설명 |
|---|---|---|
| POST | `/chat` | 대화로 일정 생성·수정. `session_id`를 계속 보내면 이전 대화를 기억 |
| DELETE | `/chat/{session_id}` | 대화 초기화 |
| POST | `/recommend` | (단발) 조건을 한 번에 넘겨 추천 받기 |
| GET | `/risks?region=부산&area=해운대&days_back=7` | 지역 이슈 뉴스만 조회 (LLM 없음). 저장 일정 알림용 |
| GET | `/regions` | 지원 시도 목록 |
| GET | `/health` | 서버 상태 확인 |

```bash
# 처음: session_id 없이 호출 → 응답의 session_id를 이후 요청에 계속 사용
curl -X POST http://localhost:8000/chat -H "Content-Type: application/json" \
  -d '{"message": "이번 주말에 부산 가려고 해요"}'
curl -X POST http://localhost:8000/chat -H "Content-Type: application/json" \
  -d '{"session_id": "<위 응답의 session_id>", "message": "커플이고 바다 보면서 조용히 걷고 싶어요"}'
```

**`/chat` 응답 필드**

| 필드 | 내용 |
|---|---|
| `session_id` | 다음 요청에 그대로 보낼 값 |
| `reply` | 마크다운 답변 (화면에 그대로 표시) |
| `stage` | `asking`(정보 수집 중) / `planned`(일정 완성) |
| `slots`, `missing` | 파악한 조건 / 더 필요한 정보 |
| `plan[]` | 일자별: `date, theme, weather, air, outdoor_ok, items[slot, note, place{name, type, address, indoor, image, mapx, mapy}]` |
| `conditions[]`, `risks[]`, `used_sources[]` | 일자별 날씨·미세먼지 / 이슈 뉴스 / 사용 데이터 |
| `caveats[]`, `timings`, `llm_stats` | `DEV_MODE=on`이거나 요청에 `"debug": true`를 보냈을 때만 채워짐 (백엔드는 관리자 계정에만 `debug`를 허용) |

세션은 서버 메모리에 2시간 보관됩니다 (서버를 재시작하면 사라짐).

**`/recommend` 요청 예**

```json
{ "region": "부산", "area": "해운대", "start_date": "2026-10-10", "end_date": "2026-10-11",
  "preferences": "조용한 바다 산책", "party": "커플", "top_n": 5 }
```

---

## 환경 변수 (.env)

`rag_project/.env` 파일을 만들고 아래처럼 채웁니다. **`.env`는 절대 깃에 올리지 마세요.**

```ini
PUBLIC_DATA_API_KEY=발급받은키
NAVER_CLIENT_ID=발급받은ID
NAVER_CLIENT_SECRET=발급받은Secret
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=gemma4:26b
```

### 필수 키

| 키 | 발급 / 활용신청 |
|---|---|
| `PUBLIC_DATA_API_KEY` | data.go.kr 인증키 하나로 아래 **세 서비스를 각각 활용신청** (신청 안 한 서비스는 `SERVICE ACCESS DENIED`) |
| ↳ 관광정보 | 한국관광공사_국문 관광정보 서비스_GW |
| ↳ 날씨 | 기상청_단기예보 조회서비스 |
| ↳ 미세먼지 | **한국환경공단_에어코리아_대기오염정보** (예보통보 + 시도별 실시간). `통합대기환경지수(CAI)`만 신청했다면 추가 신청 |
| `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET` | 네이버 클라우드 콘솔 > **NAVER API HUB** > Application > [인증 정보]. Application에 `뉴스` API가 등록돼 있어야 함 |
| Ollama | 키 없음. `OLLAMA_MODEL`은 `ollama list`에 보이는 이름과 정확히 같아야 함 |

Encoding/Decoding 키는 어느 쪽을 넣어도 동작합니다. 문화정보·교통량 API는 여행 플래너에서 쓰지 않으므로 신청하지 않아도 됩니다.

### 선택 옵션 (기본값 권장)

| 키 | 기본값 | 설명 |
|---|---|---|
| `OLLAMA_TIMEOUT` | 300 | LLM 응답 대기(초). 느린 PC는 600 |
| `OLLAMA_FALLBACK_MODEL` | (없음) | 기본 모델이 500 오류로 못 뜰 때 대신 쓸 작은 모델 (예: `gemma3:4b`) |
| `OLLAMA_THINK` | (없음) | `false`면 모델의 '생각' 단계를 꺼서 빨라짐 (gemma4 등) |
| `OLLAMA_NUM_CTX` | 8192 | 컨텍스트 길이. 결과가 이상하면 늘리기 |
| `OLLAMA_KEEP_ALIVE` | 30m | 모델을 메모리에 유지하는 시간 |
| `CHAT_MAX_CANDIDATES` | 40 | LLM에 보낼 후보 장소 수 (느리면 20) |
| `MAX_TRIP_DAYS` | 7 | 한 번에 짜는 최대 일수 |
| `GATHER_TIMEOUT_SEC` | 40 | 외부 데이터 수집 최대 대기(초). 넘은 항목은 빼고 진행 |
| `API_CACHE` | on | API 응답 캐시 (`cache/api/`). `off`로 끔 |
| `CHAT_EXTRACT_LLM_MIN_CHARS` | 40 | 이 글자 수 이상일 때만 AI로 정보 추출 (짧은 답은 규칙으로) |
| `DEV_MODE` | off | `on`이면 화면/API에 API 오류·소요 시간 등 디버그 정보 표시. **서비스에서는 끄기** |

---

## 문제 해결

### 여행지가 안 불러와질 때 → `python diagnose_api.py`

| 판정 | 의미 |
|---|---|
| `등록되지 않은 인증키` | 키 복사 오류, 또는 활용신청 승인/동기화 전 (수 분~수 시간) |
| `접근 권한이 없습니다` | 그 서비스를 활용신청하지 않았거나 승인 대기 |
| `일일 호출 한도 초과` | 개발계정 호출 한도. 내일 다시 하거나 운영계정 신청 |
| `HTTP 404` | 엔드포인트 URL 오류 (`config.py`의 `ENDPOINTS`) |
| `정상 (0건)` | 키·API는 정상인데 조건에 맞는 데이터가 없음 |
| `시간 초과` | 제공기관 서버가 느린 것 (에어코리아가 가끔). 앱은 자동 재시도 후 그 항목만 빼고 진행 |
| 네이버 `401`/`403` | Client ID/Secret이 바뀌었거나 공백/따옴표 포함, 또는 `뉴스` API 미등록. `python diagnose_api.py naver` |
| 네이버 `429` | 호출이 몰림. 자동 재시도로 완화됨 |

### Ollama 관련

- **연결 안 됨**: `python diagnose_api.py ollama`로 `.env` 주소와 `localhost` 중 어느 쪽이 되는지 확인. 같은 PC면 `OLLAMA_BASE_URL=http://localhost:11434`가 가장 안정적이에요.
- **`llama-server startup failed` (500)**: 메모리 부족. `OLLAMA_MODEL`을 작은 모델로 바꾸거나 `OLLAMA_FALLBACK_MODEL=gemma3:4b` 지정 (`ollama pull`로 미리 받기).
- **너무 느림 / 시간 초과**: 모델 파일이 RAM+VRAM보다 크면 극도로 느려집니다. `ollama run <모델> --verbose "안녕"`의 `eval rate`가 초당 10토큰 이상이면 일정 1~2분, 3토큰이면 4분 가까이 걸려요. 작은 모델(`gemma4:e4b`), `OLLAMA_THINK=false`, `CHAT_MAX_CANDIDATES=20`을 시도하세요.
- **AI가 빈 응답**: `OLLAMA_THINK=false`.

### 디버그 정보 보기

1. `.env`에 `DEV_MODE=on` → Streamlit 재시작
2. 사이드바의 **"디버그 정보 표시"** 체크 (사이드바는 왼쪽 위 `>`로 펼치기)
3. 답변 아래 **"🧪 디버그 정보"**에 API 실패 사유, 단계별 소요 시간, AI 속도가 표시됩니다.

`python check_setup.py chat`도 데이터 수집 / 후보 검색 / AI 일정 시간과 초당 토큰 수를 보여줍니다.

---

## 동작 원리

```
사용자 ↔ 챗봇 (같은 session_id로 이어지는 대화)
 │
 ├─ 정보 수집 대화: 지역 → 출발일 → 기간 → [한 번만] 동행·취향을 하나씩 되묻기      travel/chat.py
 │     지역/날짜는 규칙 파서가 우선(내일, 이번 주말, 2박 3일 ...), 동행/취향은 LLM       travel/dates.py, regions.py
 │
 ├─ 정보가 모이면 외부 데이터를 병렬 수집 (같은 여행 조건에서는 재사용)                 travel/context.py
 │     ① TourAPI 관광지·문화시설·레포츠·축제    ② 네이버 뉴스(특보/취소/통제)
 │     ③ 기상청 단기예보(오늘~3일)            ④ 에어코리아 미세먼지(오늘~모레 예보 + 실시간)
 │
 ├─ 일자별 컨디션 계산: 비/눈, 폭염·한파, 미세먼지·초미세먼지 '나쁨' → "실내 위주"     travel/conditions.py
 ├─ 후보를 임베딩 검색(취향 유사도) + 궂은 날용 실내 후보 보장 → 소개글 보강             travel/context.py
 ├─ LLM이 일자별 일정을 JSON으로 생성 (후보 id로만 장소 지정)                        travel/planner.py
 ├─ 검증: 없는 장소·중복 제거, 날짜 맞추기 / 실패 시 규칙 기반 기본 일정으로 대체
 └─ 답변 렌더링: 날씨·미세먼지 수치는 코드가 직접 채움, 궂은 날 실외 일정이 많으면 경고
```

**설계 포인트**
- **날씨·미세먼지 판단은 코드가 합니다.** LLM은 결론과 수치를 받기만 하고, 화면의 수치도 코드가 직접 채워서 지어낼 수 없습니다.
- 장소는 `C1`, `C2` 같은 **후보 id로만** 지정하게 하고 서버가 실제 정보로 되돌립니다. 후보에 없는 장소는 버립니다.
- **LLM이 죽어도 대화가 이어집니다.** 정보 추출은 규칙으로, 일정은 날씨를 반영한 기본 배치로 대체합니다.
- 일정이 나온 뒤에는 "내일 비 와요?" 같은 질문으로 출발일이 바뀌지 않도록, **변경 의도가 있을 때만** 지역·날짜를 바꿉니다.
- 시도 코드는 하드코딩하지 않고 `ldongCode2`에서 이름으로 찾습니다 (행정구역 통합 대비).
- 새 지역을 말하면 이전 지역 데이터는 초기화되고, 지역 이름 없는 수정 요청은 기존 일정을 고칩니다.

### 일정 출력 형식

AI는 **날짜별로 방문할 장소와 순서**만 정하고, 나머지는 코드가 채웁니다.

```
### 📅 1일차 · 10/7(수) — 컨셉
☀️ 맑음 · 11~23℃ · 강수확률 0%  |  😷 미세먼지 좋음 · 초미세먼지 좋음 (예보)
- **10:00 - 11:30** | **장소명** (관광지 · 🌳 실외) — 활동 설명
  - 📍 위치: 주소
- 🚶 11:30 - 11:45 | 이동: 장소A ➔ 식당B (도보 약 10분)
- **11:45 - 12:55** | 🍽️ **점심 식사: 식당명**
  - 📍 위치: 주소
```
- 시각은 **유형별 체류 시간**(관광지 90분, 문화시설 100분, 레포츠 120분 등)으로 계산합니다.
- **이동 시간은 좌표(mapx/mapy) 기반 추정**입니다 (직선거리×1.3, 1.2km 미만 도보 / 그 이상 대중교통·차량). 실제 길찾기가 아니에요.
- **점심·저녁 식당**은 직전 장소에서 가까운 TourAPI 음식점 중 고르고, 여행 중 같은 식당은 반복하지 않습니다.
- 예보 범위 밖의 날은 계절 안내(예: "이맘때는 선선한 가을 날씨예요")를 보여줍니다.

### 답변 정책

- 모든 답변 끝에 고정 문구 `🛠 개발자 정보 (제약사항·한계)`가 붙습니다 (첫 인사말 제외).
- API 오류·소요 시간 같은 **동적 내부 정보는 사용자에게 나오지 않습니다** (`DEV_MODE=on`일 때만).
- "개발자 정보", "프롬프트" 등을 물으면 서비스 소개 문구로만 답합니다.
- 뉴스는 네이버 검색 결과의 제목·요약만 쓰고 AI로 가공하지 않아요 (지어내지 않고 빠름).
- 맛집의 메뉴·영업시간은 TourAPI `detailIntro2` 값이며, 데이터에 없는 항목은 지어내지 않고 생략합니다.

---

## 폴더 구조

```
rag_project/
├── chat_app.py            # ★ 채팅 화면 (Streamlit)
├── api_server.py          # ★ FastAPI: /chat, /recommend, /risks, /regions, /health
├── diagnose_api.py        # ★ 키 문제 vs API 문제 진단
├── check_setup.py         # 단계별 점검
├── config.py              # 설정 (.env 읽기, API 엔드포인트)
├── travel/
│   ├── chat.py            # ★ 대화형 플래너 handle_message()
│   ├── planner.py         # 프롬프트, LLM 응답 검증, 기본 일정, 마크다운 렌더링
│   ├── schedule.py, geo.py   # 시간표(체류·이동·식사), 좌표 기반 이동 시간 추정
│   ├── conditions.py      # 일자별 날씨·미세먼지 → 실내/실외 판단
│   ├── context.py         # 데이터 수집·후보 선별
│   ├── dates.py           # 한국어 날짜 파서
│   ├── lists.py, placeinfo.py, news.py, multi.py   # 목록·장소 문의·뉴스·다중 지역
│   ├── regions.py, ldong.py, gazetteer.py, places.py, risk_scanner.py
│   └── pipeline.py        # (단발 추천) recommend_trip()
├── collectors/            # TourAPI, 기상청, 에어코리아, 네이버 등 API 클라이언트 + 캐시
├── rag/                   # ChromaDB 벡터 스토어 (app.py용)
├── llm/ollama_client.py   # Ollama 호출, JSON 파싱
├── tests/                 # 키/Ollama 없이 돌리는 오프라인 테스트
├── travel_app.py, app.py  # (이전) 단발 추천 화면 / 범용 챗봇
└── cache/                 # 실행 중 자동 생성 (API 응답·임베딩·지역 사전). 깃에 올리지 않음
```

---

## 알아둘 점 / 한계

- **날씨는 약 3일, 미세먼지는 오늘~모레**까지만 예보가 있습니다. 그 밖의 날짜는 반영하지 못합니다.
- **실내/실외 구분**은 장소 이름과 유형으로 추정한 값이라 틀릴 수 있습니다.
- **뉴스 이슈**는 최근 7일 기사 기준이라 여행일이 멀수록 현재 상황과 달라질 수 있어요.
- **로컬 LLM은 한 번에 하나씩 처리**합니다. 첫 일정 요청이 가장 느리고(데이터 수집 + 모델 로드), 수정 요청은 훨씬 빠릅니다.
- **캐시**: API 응답은 `cache/api/`에 저장됩니다 (관광정보 12시간, 날씨·예보 30분, 뉴스 10분). API가 실패하면 최근 저장본(미세먼지 18시간, 날씨·뉴스 6시간, 관광정보 며칠)으로 대신 답합니다. 초기화하려면 `cache/` 폴더를 지우세요 (다시 자동 생성).
- **세션**은 API 서버 메모리에만 있어 재시작하면 사라집니다. 서버를 여러 대로 늘릴 때는 Redis 등으로 옮겨야 합니다.
- **TourAPI는 KorService2**입니다. 엔드포인트/파라미터는 `config.py`, `collectors/tourism.py`에 있습니다.
