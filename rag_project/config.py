"""
전역 설정 파일
.env 파일에서 API 키들을 불러옵니다.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ══════════════════════════════════════════════════════════════════════
# ★ API 키는 이 파일에 직접 쓰지 말고, 프로젝트 루트의 `.env` 파일에 넣으세요. ★
#   (.env.example 을 복사해서 .env 를 만들고 값을 채우면 됩니다)
# ══════════════════════════════════════════════════════════════════════

# ── 공공데이터포털 서비스키 (5개 공공데이터 API가 모두 이 키 하나를 공유) ──
# ★ 넣을 곳: .env 의 PUBLIC_DATA_API_KEY=
# https://www.data.go.kr 마이페이지 > 오픈API > 활용신청 내역에서 발급받은 키
# (Encoding 키/Decoding 키 중 하나. 인증 오류가 나면 다른 쪽 키로 바꿔서 시도)
PUBLIC_DATA_API_KEY = os.getenv("PUBLIC_DATA_API_KEY", "")

# ── 네이버 검색/데이터랩 API ────────────────────────────────────────────
# ★ 넣을 곳: .env 의 NAVER_CLIENT_ID=  /  NAVER_CLIENT_SECRET=
# 발급: NAVER API HUB(네이버 클라우드 콘솔 > NAVER API HUB > Application > 해당 앱의 [인증 정보])
# Client ID → NAVER_CLIENT_ID, Client Secret → NAVER_CLIENT_SECRET
# (Application의 API 목록에 '뉴스'가 등록돼 있어야 함)
NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID", "").strip()
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET", "").strip()

# ── Ollama (로컬 LLM) ─────────────────────────────────────────────────
# ollama가 로컬에서 서비스 중인 주소 (기본 설치 시 그대로 사용하면 됨)
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").strip().rstrip("/")  # 끝의 / 는 자동 제거
# 사전에 `ollama pull <모델명>`으로 받아둔 모델명을 지정하세요.
# ★ 모델명은 `ollama list` 에 표시되는 이름과 정확히 같아야 합니다. (API 키 불필요)
OLLAMA_FALLBACK_MODEL = os.getenv("OLLAMA_FALLBACK_MODEL", "").strip()  # 기본 모델이 500으로 못 뜰 때 대신 쓸 작은 모델 (예: gemma3:4b)
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma4:26b")
# 26B급 모델은 응답이 느릴 수 있어 넉넉하게 (초)
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "300"))
# 프롬프트(후보 장소+뉴스+날씨)가 길어서 컨텍스트를 키워둠. 너무 작으면 앞부분이 잘려 엉뚱한 답이 나옴.
OLLAMA_NUM_CTX = int(os.getenv("OLLAMA_NUM_CTX", "8192"))
# 모델을 메모리에 올려둘 시간. 기본(5분)이면 잠깐 쉬었다 대화할 때마다 모델을 다시 올려 느려지므로 길게 잡음
OLLAMA_KEEP_ALIVE = os.getenv("OLLAMA_KEEP_ALIVE", "30m")
# 일부 모델은 답하기 전에 길게 '생각'해서 느리거나 빈 응답을 줍니다. false로 끄면 빨라질 수 있어요.
# 비워두면 옵션을 보내지 않습니다(모델 기본 동작). 생각 기능이 없는 모델에는 보내지 않는 게 안전해요.
OLLAMA_THINK = os.getenv("OLLAMA_THINK", "").strip().lower()   # "" | "true" | "false"

# ── 벡터 DB / 임베딩 ──────────────────────────────────────────────────
# 로컬 무료 임베딩 모델 (다국어 지원, 한국어 성능 준수)
EMBEDDING_MODEL_NAME = os.getenv(
    "EMBEDDING_MODEL_NAME", "paraphrase-multilingual-MiniLM-L12-v2"
)
CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
# 장소 임베딩을 저장해 두는 파일. 처음 본 장소만 계산하므로 두 번째 요청부터 후보 검색이 거의 즉시 끝납니다.
EMBED_CACHE_PATH = os.getenv("EMBED_CACHE_PATH", "./cache/place_embeddings.npz")

# ── 검색 시 반환할 문서 개수 ──────────────────────────────────────────
TOP_K = int(os.getenv("TOP_K", "5"))

# ── 여행지 추천 RAG 설정 ──────────────────────────────────────────────
TRAVEL_CANDIDATE_TOP_K = int(os.getenv("TRAVEL_CANDIDATE_TOP_K", "10"))  # 벡터검색으로 뽑을 후보 수
TOUR_ROWS_PER_TYPE = int(os.getenv("TOUR_ROWS_PER_TYPE", "200"))         # (시도 단위) 관광타입별 TourAPI 조회 개수
TOUR_AREA_ROWS = int(os.getenv("TOUR_AREA_ROWS", "1000"))                # (시군구 단위) 한 번에 받을 최대 개수. 시군구는 보통 수백 건이라 전부 받음
NEWS_DAYS_BACK = int(os.getenv("NEWS_DAYS_BACK", "7"))                   # 리스크 뉴스로 볼 최근 일수
# 후보 장소 소개글(detailCommon2)을 요청당 최대 몇 건까지 새로 조회할지. 0이면 끔.
# (TourAPI 개발계정은 일일 호출 한도가 있어 결과를 파일로 캐시함)
OVERVIEW_ENRICH_LIMIT = int(os.getenv("OVERVIEW_ENRICH_LIMIT", "30"))
OVERVIEW_CACHE_PATH = os.getenv("OVERVIEW_CACHE_PATH", "./cache/overview_cache.json")

# ── 챗봇 설정 ──────────────────────────────────────────────────────────
# 이 글자 수 이상인 메시지에서만 'AI 정보 추출'을 씁니다. 짧은 답("부산 가려고요", "내일부터 2박 3일")은
# 규칙으로 충분해서 AI 호출을 아껴 빨라집니다. 0이면 항상 사용합니다.
CHAT_EXTRACT_LLM_MIN_CHARS = int(os.getenv("CHAT_EXTRACT_LLM_MIN_CHARS", "40"))
# 외부 API(관광정보/날씨/미세먼지/뉴스) 응답을 잠시 저장해 같은 요청을 반복하지 않게 합니다. off로 끌 수 있어요.
# 개발 모드: 켜져 있을 때만 API 오류·제약사항·소요 시간 같은 내부 정보가 화면/API 응답에 나옵니다.
# 서비스(사용자 화면)에서는 항상 꺼두세요. 개발·점검할 때만 .env에 DEV_MODE=on
DEV_MODE = os.getenv("DEV_MODE", "off").strip().lower() in ("on", "1", "true", "yes")
API_CACHE_ENABLED = os.getenv("API_CACHE", "on").strip().lower() not in ("off", "0", "false")
API_CACHE_DIR = os.getenv("API_CACHE_DIR", "./cache/api")
# 일정 만들 때 외부 데이터를 모으는 최대 대기 시간(초). 이 시간까지 안 끝난 항목은 빼고 진행합니다.
GATHER_TIMEOUT_SEC = float(os.getenv("GATHER_TIMEOUT_SEC", "40"))
CHAT_MAX_CANDIDATES = int(os.getenv("CHAT_MAX_CANDIDATES", "40"))   # LLM에 보낼 후보 장소 최대 수 (줄이면 빨라짐)
CHAT_MAX_NEWS = int(os.getenv("CHAT_MAX_NEWS", "8"))                # LLM에 보낼 이슈 뉴스 최대 수
MAX_TRIP_DAYS = int(os.getenv("MAX_TRIP_DAYS", "7"))              # 한 번에 짜줄 최대 일수
CHAT_HISTORY_TURNS = int(os.getenv("CHAT_HISTORY_TURNS", "6"))    # LLM에 같이 보낼 최근 대화 턴 수
CONTEXT_TTL_SEC = int(os.getenv("CONTEXT_TTL_SEC", "1800"))       # 수집한 데이터를 재사용하는 시간(초)
LDONG_CACHE_PATH = os.getenv("LDONG_CACHE_PATH", "./cache/ldong_codes.json")
GAZETTEER_CACHE_PATH = os.getenv("GAZETTEER_CACHE_PATH", "./cache/gazetteer.json")  # 전국 시군구 이름 사전

# ── 각 공공데이터포털 API 엔드포인트 ─────────────────────────────────
# 주의: data.go.kr에서 "활용신청" 승인 후 마이페이지에서 정확한 요청 URL을
# 다시 한 번 확인하세요. 기관별로 baseURL이 조금씩 다를 수 있습니다.
ENDPOINTS = {
    # 한국관광공사_국문 관광정보 서비스_GW (KorService2)
    "tourism": "https://apis.data.go.kr/B551011/KorService2/areaBasedList2",
    "tour_festival": "https://apis.data.go.kr/B551011/KorService2/searchFestival2",
    "tour_detail": "https://apis.data.go.kr/B551011/KorService2/detailCommon2",
    "tour_search": "https://apis.data.go.kr/B551011/KorService2/searchKeyword2",  # 장소 이름 검색
    "tour_intro": "https://apis.data.go.kr/B551011/KorService2/detailIntro2",  # 음식점 대표메뉴·영업시간·주차 등
    "tour_area_code": "https://apis.data.go.kr/B551011/KorService2/areaCode2",
    # 법정동 시도 코드 목록 (행정구역이 바뀌어도 코드를 이름으로 찾기 위해 사용)
    "tour_ldong": "https://apis.data.go.kr/B551011/KorService2/ldongCode2",
    # 에어코리아 대기오염정보: 미세먼지/초미세먼지 예보통보 (오늘~모레)
    "air_forecast": "https://apis.data.go.kr/B552584/ArpltnInforInqireSvc/getMinuDustFrcstDspth",
    # 기상청_단기예보 조회서비스
    "weather": "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst",
    # 한국문화정보원_한눈에보는문화정보조회서비스
    "culture": "https://apis.data.go.kr/B553457/nation-festival/festival",
    # 한국환경공단_에어코리아_통합대기환경지수(CAI) 조회 서비스
    "air_quality": "https://apis.data.go.kr/B552584/ArpltnInforInqireSvc/getCtprvnRltmMesureDnsty",
    # 국토교통부_한국건설기술연구원 교통량 통계 데이터 정보조회서비스
    "traffic": "https://apis.data.go.kr/1613000/TrafficVolumeService/getTrafficVolumeList",
    # 네이버 검색/검색어 트렌드: NAVER API HUB
    "naver_news_hub": "https://naverapihub.apigw.ntruss.com/search/v1/news",
    "naver_datalab_hub": "https://naverapihub.apigw.ntruss.com/search-trend/v1/search",
}
