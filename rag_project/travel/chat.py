"""
대화형 여행 플래너.

한 턴의 흐름 (handle_message)
  1) 사용자 메시지에서 지역·날짜·동행·취향을 추출
       - 지역/날짜는 규칙 파서가 우선 (작은 로컬 LLM이 날짜 계산을 틀리는 것을 방지)
       - 동행/취향/피할 것은 LLM이 추출. LLM이 죽어도 규칙으로 계속 진행
  2) 부족한 정보가 있으면 하나씩 되묻기 (지역 → 출발일 → 기간 → [한 번만] 동행·취향)
  3) 정보가 모이면 데이터 수집(관광정보·뉴스·날씨·미세먼지) → 후보 검색 → LLM이 일자별 일정 생성
  4) 일정이 나온 뒤의 메시지는 '수정/질문'으로 처리 (이미 모은 데이터를 재사용해 빠르게 응답)
"""
import copy
import json
import re
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import date, timedelta

from config import (
    DEV_MODE, CHAT_EXTRACT_LLM_MIN_CHARS, CHAT_HISTORY_TURNS, CHAT_MAX_CANDIDATES, CHAT_MAX_NEWS, CHAT_PLAN_CHUNK_DAYS,
    CONTEXT_TTL_SEC, INTRO_PLAN_LIMIT,
    MAX_TRIP_DAYS, NEWS_DAYS_BACK,
)
from collectors.tourism import enrich_intro
from llm.ollama_client import LAST_STATS, chat_json_messages
from collectors.naver_local import search_local
from travel.clock import hhmm, parse_stay_times, parse_time_range
from travel.userplaces import NO_LODGING_RE, find_place, integrate, key_of, lodging_item_from_reply, parse_directives
from travel.conditions import build_day_conditions, display_line, prompt_line
from travel.context import enrich, gather_raw, rank_places, select_candidates
from travel.dates import (WD, date_in_month, day_of_month, fmt_korean, fmt_md, normalize_casual, parse_iso,
                          parse_trip_dates)
from travel.geo import _coord, district_of, straight_km
from travel.gazetteer import METRO, ambiguous_regions, lookup_in_sido, lookup_regions
from travel.lists import answer_list, one_liner
from travel.places import SIGHT_TYPES
from travel.news import NEWS_RE, SAFETY_ASK_RE, answer_news, parse_news_request
from travel.placeinfo import answer_place, is_place_info_request
from travel.evaluation import evaluate_plan
from travel.multi import parse_multi_trips
from travel.pipeline import FORECAST_DAYS, _collect_candidates, _collect_festivals, _collect_type, wants_food
from travel.planner import (
    PLAN_SYSTEM_PROMPT, build_plan_user_message, fallback_plan, fill_thin_days, hydrate_plan, normalize_plan,
    render_markdown,
)
from travel.regions import SIDO, _mentions, mentioned_regions, resolve_place
from travel.profile import push_visited_back, taste_words
from travel.routing import fix_closures, rebalance_days
from travel.schedule import stay_minutes

GREETING = (
    "지역과 원하는 것을 말씀해 주세요.\n"
    "- 여행지·맛집·숙소·축제: \"성남 가볼 만한 곳 추천해줘\", \"분당 맛집 알려줘\", \"부산 숙소 추천해줘\"\n"
    "- 일정: \"성남 7일 일정 짜줘\", \"대구 1박2일, 부산 2박3일 짜줘\"\n"
    "- 특정 장소·지역 소식: \"모란시장 정보 알려줘\", \"성남 요즘 소식 있어?\""
)

# 모든 답변의 맨 끝에 붙는 고정 하단 서식 (실제 API 오류·소요 시간 같은 동적 내부 정보는 포함하지 않는다)
FOOTER_TITLE = "🛠 개발자 정보 (제약사항·한계)"
FOOTER = (
    "\n\n---\n"
    f"{FOOTER_TITLE}\n\n"
    "- 본 서비스는 한국관광공사 TourAPI 4.0 국문 관광정보 API 및 공공데이터를 기반으로 동작합니다.\n"
    "- 날씨 및 미세먼지 예보는 기상청 단기예보 기준이며 세부 지역에 따라 다를 수 있습니다.\n"
    "- 실내/실외 구분은 장소 이름 및 카테고리 속성값으로 추정한 결과이므로 방문 전 재확인이 필요합니다.\n"
    "- 관광지, 식당, 숙박시설의 운영시간, 휴무일, 입장료는 방문 전 사전 확인을 권장합니다."
)

# 개발자 정보·시스템 정보·제약사항 같은 내부 정보를 묻는 말에는 어떤 내부 내용도 보여주지 않고 이 문구로만 답한다
ABOUT_RE = re.compile(r"개발자\s*정보|시스템\s*정보|제약\s*사항|디버그|에러\s*로그|오류\s*로그|내부\s*정보|프롬프트|API\s*(오류|에러|키)|너\s*(누구|뭐야|뭐하)|무슨\s*서비스|누가\s*만들", re.I)
ABOUT_REPLY = "본 서비스는 한국관광공사 TourAPI 및 최신 위치 데이터를 활용하여 맞춤형 여행 정보와 일정을 제공하는 AI 가이드입니다."

# 요청 유형 판별 (일정 / 단발 여행지 추천 / 단발 맛집·카페)
PLAN_RE = re.compile(r"일정|코스|계획|플랜|스케줄|\d+\s*박|\d+\s*일\s*(?:간|동안|여행)|짜\s*줘")
FOOD_RE = re.compile(r"맛집|식당|밥집|음식점|먹거리|먹을|카페|커피|디저트|브런치|술집")
RECO_RE = re.compile(r"어디가\s*좋|어디\s*갈까|어디\s*가지|어디\s*가면\s*좋|추천|가볼\s*만한|가볼만한|명소|관광지|볼거리|놀거리|구경|데이트\s*장소|갈\s*만한|핫플|여행지")
ASK_RE = re.compile(r"알려|추천|보여|찾아|어디|뭐\s*있|뭐가\s*있|있을까|가볼|\?")
STAY_RE = re.compile(r"숙박|숙소|호텔|펜션|리조트|모텔|게스트하우스|한옥\s*스테이|민박|묵을|잘\s*곳")
FEST_RE = re.compile(r"축제|행사|공연|페스티벌|이벤트")
# 축제 질문이라도 이런 말이 있으면 일정 요청 ("축제 위주로 일정 짜줘", "축제도 넣어줘")
# 일정이 있거나 동행·취향을 묻는 중에 축제를 "목록으로 달라"는 뜻으로 볼 표현 ("이 기간에 하는 축제 있어", "축제 언제 해")
FEST_ASK_RE = re.compile(r"있어|있나|있니|열리|하는|언제|일정|스케줄")
FEST_PLAN_RE = re.compile(r"짜|계획|플랜|만들어|위주|중심|포함|넣어|추가|코스")
# 축제를 '찾아 달라/추천해 달라'는 말 ("괜찮은 축제 있나 찾아줘"): 일정에 바로 넣지 않고 후보만 보여주고, 사용자가 고르면 추가한다
FEST_RECO_RE = re.compile(r"찾아|추천|있나|있을까|있어|있니|알려|괜찮은|볼\s*만한|볼만한|좋은|어때")
# 축제를 일정의 중심으로 삼으라는 말 ("축제 위주로", "축제 방문 기준으로", "축제 넣어서 짜줘")
FEST_FOCUS_RE = re.compile(r"위주|중심|기준|방문|맞춰|포함|꼭|참여|보러|넣어|넣고|들어가")
# 여행을 간다는 말투 ("여행을 가는데 일정이 비어서 축제 찾아줘"): 축제 목록만이 아니라 일정도 함께 짜 달라는 뜻
FEST_TRIP_RE = re.compile(r"가는데|갈\s*예정|갈\s*거|갈\s*건데|갈\s*계획|가려고|여행(?:을|이)?\s*가|일정이\s*(?:좀\s*)?(?:비|남|부족|허전)|비어")
# 추천받은 축제를 고르는 말: 추가해 달라 / 마음에 든다 / 네(추가할까요?에 대한 답)
FEST_ADD_RE = re.compile(r"추가|넣어|넣자|넣을|끼워|포함|이걸로|이거로|그걸로|저걸로|갈래|가자|할래|정할래|골랐")
FEST_POS_RE = re.compile(r"괜찮|좋아|좋네|좋은데|좋겠|마음에|가보고\s*싶|가고\s*싶|끌려|땡겨|재밌겠|재미있겠")
FEST_YES_RE = re.compile(r"^\s*(?:네|넵|예|응|어|그래|좋아|좋아요|ㅇㅇ|오케이|ok|넣어줘|추가해줘|추가|부탁해|부탁해요)", re.I)
# 축제를 물을 때 "이 기간", "여행 때"처럼 이미 정한 여행 날짜를 가리키는 말
PERIOD_REF_RE = re.compile(r"(?:이|그|여행|일정)\s*(?:기간|때|동안|날짜)|그때|여행\s*중|가는\s*날")
MONTH_ONLY_RE = re.compile(r"(\d{1,2})\s*월(?!\s*\d{1,2}\s*일)")
FEST_DAYS_AHEAD = 60  # 날짜를 말하지 않은 축제 질문은 오늘부터 이 기간에 열리는 것
COURSE_LIST_RE = re.compile(r"추천\s*여행\s*코스|추천\s*코스|여행\s*코스\s*(목록|리스트)|코스\s*(목록|리스트)")
LIST_INTENTS = ("recommend", "food", "stay", "festival", "course")
MODIFY_RE = re.compile(r"넣어|추가|바꿔|빼|변경|수정|교체|대신|다시|늘려|줄여")

CHANGE_RE = re.compile(r"(바꿔|바꾸|변경|옮겨|미뤄|당겨|출발|떠나|말고|대신|로 갈|으로 갈|로 가|으로 가|갈래|가고 싶|다시 짜|새로)")
DATE_HINT_RE = re.compile(r"\d|오늘|내일|낼|모레|글피|주말|다음|이번|저번|지난|담주|담달|요일|욜|당일|이틀|사흘|나흘|크리스마스|성탄")
RESET_RE = re.compile(r"(처음부터|새로 시작|초기화|리셋|다시 시작)")
ACTIVITY_RE = re.compile(r"액티비티|레포츠|체험|서핑|요트|낚시|등산|스포츠|래프팅|패러|스키|카트")
EMPTY_ANSWER_RE = re.compile(r"^(상관\s*없|없음|없어|없습니다|모름|딱히|x$|-$)")

PARTY_PATTERNS = [
    ("커플", r"커플|연인|애인|남자친구|여자친구|남친|여친|신혼"),
    ("혼자", r"혼자|나홀로|솔로"),
    ("아이 동반 가족", r"아이|아기|유아|애들|아들|딸"),
    ("부모님과 함께", r"부모님|엄마|아빠|어머니|아버지"),
    ("친구", r"친구"),
    ("가족", r"가족"),
]

EXTRACT_SYSTEM = """너는 여행 플래너 챗봇의 '정보 추출기'다. 사용자의 최신 메시지와 대화 맥락에서 여행 조건을 뽑아 JSON으로만 답한다.

규칙
- 사용자가 실제로 말한 내용만 채운다. 말하지 않은 값은 "" 로 둔다. 추측하지 마라.
- region은 17개 시도명 중 하나: 서울, 부산, 대구, 인천, 광주, 대전, 울산, 세종, 경기, 강원, 충북, 충남, 전북, 전남, 경북, 경남, 제주.
  시·군·명소를 말하면 해당 시도를 region에, 그 이름을 area에 쓴다. (예: 경주 → region 경북, area 경주)
- start_date, end_date는 YYYY-MM-DD. 오늘 날짜 기준으로 계산하고, 'N박M일'이면 end_date = start_date + N일. 모르면 "".
- party: 동행(혼자/커플/친구/가족/아이 동반/부모님 등). preferences: 원하는 분위기·활동을 짧은 구절로(쉼표로 구분). avoid: 싫어하거나 피하고 싶은 것.
- 사용자가 '상관없어요/없어요'라고 하면 해당 항목은 "".

출력 형식: {"region":"","area":"","start_date":"","end_date":"","party":"","preferences":"","avoid":""}"""


# ── 세션 ──────────────────────────────────────────────────────────────
def _empty_slots() -> dict:
    return {"region": "", "area": "", "start_date": "", "end_date": "", "nights": None,
            "party": "", "preferences": "", "avoid": "", "date_hint": None}


def _province_city(text: str) -> tuple[str, str] | None:
    """'경기 광주'처럼 도 이름 바로 뒤에 광역시와 이름이 같은 그 도의 시가 오면 (도, 시). 아니면 None."""
    ms = _mentions(text)
    for (_, b, s1, _, d1), (c, _, s2, tok2, d2) in zip(ms, ms[1:]):
        if d1 and d2 and s1 not in METRO and s2 in METRO and not text[b:c].strip() and lookup_in_sido(tok2, s1) == tok2:
            return s1, tok2
    return None


def regions_ext(text: str) -> list[tuple[str, str]]:
    """
    문장 속 지역을 등장 순서대로. 도시 목록에 없는 기초지자체(곡성, 영월 등)는 시군구 사전으로 보충하고,
    시도만 찾았으면 그 시도 안의 시군구 이름('강원 고성', '부산 중구')을 붙인다.
    """
    pc = _province_city(text)
    if pc:
        return [pc]
    regs = mentioned_regions(text)
    if regs:
        return [(s, a or lookup_in_sido(text, s)) for s, a in regs]
    return lookup_regions(text)


def resolve_place_ext(text: str) -> tuple[str | None, str]:
    """(시도, 세부지역). 도만 말하면 ('경기', ''), 시·군·구까지 말하면 ('경기', '성남') — 전국 시군구를 모두 인식한다."""
    pc = _province_city(text)
    if pc:
        return pc
    sido, area = resolve_place(text)
    if sido:
        return sido, area or lookup_in_sido(text, sido)
    found = lookup_regions(text)
    return found[-1] if found else (None, "")


def _prev_assistant_text(session: "ChatSession") -> str:
    """방금 들어온 사용자 메시지 바로 전의 챗봇 답변."""
    for m in reversed(session.history[:-1]):
        if m["role"] == "assistant":
            return m["content"]
    return ""


def _prev_user_text(session: "ChatSession") -> str:
    """방금 들어온 메시지 바로 전의 사용자 메시지."""
    users = [m["content"] for m in session.history if m["role"] == "user"]
    return users[-2] if len(users) >= 2 else ""


def _last_region(seg: str) -> tuple[str, str] | None:
    regs = regions_ext(seg)
    return regs[-1] if regs else None


@dataclass
class ChatSession:
    session_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    slots: dict = field(default_factory=_empty_slots)
    history: list = field(default_factory=list)       # [{"role": "user"|"assistant", "content": str}]
    raw: dict | None = None                           # 수집한 외부 데이터 (같은 여행 조건에서 재사용)
    raw_key: tuple | None = None
    plan: dict | None = None                          # 마지막으로 만든 일정 (candidate_id 기준)
    last_cand_map: dict = field(default_factory=dict)  # 마지막 일정에서 쓴 후보 id → 장소
    id_map: dict = field(default_factory=dict)        # 장소 key → 'C#' (대화 내내 같은 id 유지)
    view: dict | None = None                          # 마지막 일정의 화면용 결과
    asked_optional: bool = False
    trips: dict = field(default_factory=dict)          # 다중 지역 일정: 지역 이름 → 그 지역 전용 하위 세션
    pending_multi: dict | None = None                  # 다중 지역 일정에서 출발일을 기다리는 중
    last_festivals: list = field(default_factory=list)  # 마지막으로 보여준 축제 목록 ("저거 기준으로 다시 짜줘"용)
    restaurants: list = field(default_factory=list)    # 마지막 일정의 식사 후보 (시간만 바꿔 다시 그릴 때 재사용)
    fest_pins: dict = field(default_factory=dict)      # 일정에 들어간 축제: 장소 key → {"title","day","start","end","asked"}
    fest_times: dict = field(default_factory=dict)     # 사용자가 알려준 축제 시간: 장소 key → (시작 분, 끝 분 또는 None)
    awaiting_fest_time: bool = False                   # 축제 시간을 알려달라고 안내한 뒤 답을 기다리는 중
    user_places: list = field(default_factory=list)    # 사용자가 직접 말한 방문 장소: {"place","day_ref","time","ctx","assigned_day"}
    lodging: dict | None = None                        # 사용자가 알려준 숙소 (하루의 출발·복귀 지점)
    pending_ack: dict | None = None                    # 방금 메시지에서 읽은 장소 요약 (답변 앞에 붙임)
    rest_text: str | None = None                       # 장소 말을 뺀 나머지 말 (일반 흐름이 지역·날짜·취향을 읽을 때 쓴다)
    stay_times: dict = field(default_factory=dict)     # 사용자가 알려준 숙소 체크인·체크아웃 시각: {"in": 분, "out": 분}
    asked_stay_times: bool = False                     # 체크인·체크아웃 시각 안내를 이미 했는가 (한 번만 안내)
    want_fest_reco: bool = False                       # 축제를 추천해 달라고 했다 (일정을 만들 때 후보를 함께 보여주고 비워 둔다)
    fest_hint_day: int | None = None                   # 축제 추천을 부탁하며 말한 일차 (0부터. "둘째 날이 비어서")
    fest_pending: dict | None = None                   # 마음에 든다고만 한 축제: 추가할까요? 에 대한 답을 기다리는 중
    pending_stay: dict | None = None                   # 방금 메시지에서 읽은 체크인·체크아웃 (답변 앞 요약에 붙임)
    lodging_hold: str = ""                             # 말한 숙소를 찾지 못해 일정 만들기를 멈추고 숙소를 다시 물어보는 중 (찾은 숙소 이름)
    last_used: float = field(default_factory=time.time)
    lock: threading.RLock = field(default_factory=threading.RLock, repr=False)
    # ── 보낸 말 취소용 (처리 중 잠금(lock)과 따로 둬서 취소 요청이 처리가 끝나길 기다리지 않게) ──
    turn: int = 0                                      # 지금까지 받은 말 번호
    busy_turn: int | None = None                       # 지금 처리 중인 말 번호
    cancelled_turn: int = -1                           # 취소된 말 번호
    undo: tuple | None = None                          # (말 번호, 그 말을 받기 전 대화 기억, 끝난 시각) — 마지막 말만
    cancel_next_until: float = 0.0                     # 취소가 말보다 먼저 도착했을 때: 이 시각 전에 오는 말은 바로 취소
    turn_lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    profile: dict | None = None                        # 회원 취향 요약 (백엔드가 '내 여행' 저장 장소로 만들어 보냄)
    progress: str = ""                                 # 지금 하는 일 (답을 기다리는 화면에 보여줌). 처리 중이 아니면 ""
    progress_at: float = 0.0                           # 이번 말을 받기 시작한 시각

    def reset(self) -> None:
        self.slots, self.history = _empty_slots(), []
        self.raw = self.raw_key = self.plan = self.view = None
        self.last_cand_map, self.id_map, self.asked_optional = {}, {}, False
        self.trips, self.pending_multi, self.last_festivals = {}, None, []
        self.restaurants, self.fest_pins, self.fest_times, self.awaiting_fest_time = [], {}, {}, False
        self.user_places, self.lodging, self.pending_ack, self.lodging_hold, self.rest_text = [], None, None, "", None
        self.stay_times, self.asked_stay_times, self.pending_stay = {}, False, None
        self.want_fest_reco, self.fest_hint_day, self.fest_pending = False, None, None
        self.undo = None


# ── 보낸 말 취소 ──────────────────────────────────────────────────────
_NO_SNAPSHOT = {"session_id", "lock", "turn_lock", "last_used", "turn", "busy_turn", "cancelled_turn", "undo",
                "cancel_next_until", "progress", "progress_at", "profile"}
UNDO_WINDOW_SEC = 15  # 끝난 말은 이 시간 안에 온 취소만 받는다 (답이 오는 사이 누른 취소). 그보다 오래된 말은 되돌리지 않는다
PENDING_WINDOW_SEC = 3  # 취소가 말보다 먼저 온 경우, 이 시간 안에 오는 말만 취소 (취소 후 다시 보낸 말은 살린다)
_turn_ctx = threading.local()  # 이 스레드가 처리 중인 (세션, 말 번호) — 다중 지역의 하위 세션에서도 취소를 알아채게


class TurnCancelled(Exception):
    """사용자가 보낸 말을 취소해서 처리를 중간에 멈춘다"""


def _snapshot(s: ChatSession) -> dict:
    """대화 기억 복사본. 수집 데이터(raw)는 크고 통째로 바뀌기만 해서 참조만 둔다."""
    snap = {}
    for f in s.__dataclass_fields__:
        if f in _NO_SNAPSHOT:
            continue
        v = getattr(s, f)
        if f == "raw":
            snap[f] = v
        elif f == "trips":
            snap[f] = {k: (sub, _snapshot(sub)) for k, sub in v.items()}
        else:
            snap[f] = copy.deepcopy(v)
    return snap


def _restore(s: ChatSession, snap: dict) -> None:
    for f, v in snap.items():
        if f == "trips":
            for sub, sub_snap in v.values():
                _restore(sub, sub_snap)
            v = {k: sub for k, (sub, _) in v.items()}
        setattr(s, f, v)


def set_progress(step: str) -> None:
    """지금 하는 일을 기록한다 (GET /chat/{id}/progress 로 화면에 보임). 하위 세션에서 불러도 원래 대화에 기록된다."""
    ctx = getattr(_turn_ctx, "cur", None)
    if ctx:
        ctx[0].progress = step


def get_progress(session: ChatSession) -> dict:
    """{"busy": 처리 중인지, "step": 지금 하는 일, "elapsed": 이번 말을 받은 뒤 지난 초}"""
    with session.turn_lock:
        busy = session.busy_turn is not None
    return {"busy": busy, "step": session.progress if busy else "",
            "elapsed": round(time.time() - session.progress_at, 1) if busy else 0}


def _profile_of(session: ChatSession) -> dict | None:
    """회원 취향 요약. 여러 지역 일정의 하위 세션은 원래 대화의 것을 쓴다."""
    if session.profile is not None:
        return session.profile
    ctx = getattr(_turn_ctx, "cur", None)
    return ctx[0].profile if ctx else None


def check_cancelled() -> None:
    """오래 걸리는 일(데이터 수집·AI 호출) 직전에 불러, 취소됐으면 멈춘다."""
    ctx = getattr(_turn_ctx, "cur", None)
    if ctx and ctx[0].cancelled_turn == ctx[1]:
        raise TurnCancelled()


def cancel_turn(session: ChatSession) -> str:
    """
    사용자가 방금 보낸 말을 취소합니다. 대화 기억을 그 말을 보내기 전으로 되돌립니다.
    Returns: "running"(처리 중 → 멈추고 되돌림) | "undone"(방금 끝난 말을 되돌림)
             | "pending"(말이 아직 안 왔음 → 곧 오는 말을 처리하지 않음) | "none"(되돌릴 수 없음)
    """
    with session.turn_lock:
        if session.busy_turn is not None:
            session.cancelled_turn = session.busy_turn
            return "running"
        undo = session.undo
        if not undo or undo[0] != session.turn or time.time() - undo[2] > UNDO_WINDOW_SEC:
            # 방금 끝난 말이 없으면 취소가 보낸 말보다 먼저 도착한 것: 곧 올 그 말을 취소한다
            session.cancel_next_until = time.time() + PENDING_WINDOW_SEC
            return "pending"
    if not session.lock.acquire(timeout=5):  # 그 사이 새 말을 처리 중이면 건드리지 않는다
        return "none"
    try:
        with session.turn_lock:
            if session.undo is not undo or session.busy_turn is not None:
                return "none"
            session.undo = None
        _restore(session, undo[1])
        return "undone"
    finally:
        session.lock.release()


def _llm_json(*args, **kwargs):
    check_cancelled()
    return chat_json_messages(*args, **kwargs)


# ── 슬롯 추출 ─────────────────────────────────────────────────────────
def _clip(s: str, n: int) -> str:
    s = (s or "").replace("\n", " ")
    return s if len(s) <= n else s[:n] + "…"


def _merge_text(old: str, new: str) -> str:
    items = [x.strip() for x in re.split(r"[,;/\n]", old or "") if x.strip()]
    for x in re.split(r"[,;/\n]", new or ""):
        x = x.strip()
        if x and x not in items and not EMPTY_ANSWER_RE.match(x):
            items.append(x)
    return ", ".join(items)[:200]


def _leftover(text: str, today: date) -> str:
    """
    메시지에서 지역·날짜·기간 표현을 지우고 남은 말. 취향이 들어 있는지 판단하는 데 씁니다.
    예) "내일 당일치기 조용히 걷고 싶어요" → "조용히 걷고 싶어요",  "부산 가려고요" → "가려고요"
    """
    work = parse_trip_dates(text, today)["rest"]  # 날짜 표현은 이미 공백으로 지워짐 (줄임말을 바꾼 문장 기준)
    for a, b, *_ in _mentions(normalize_casual(text, today)):
        work = work[:a] + " " * (b - a) + work[b:]
    work = re.sub(r"\d{1,2}\s*박(?:\s*\d{1,2}\s*일)?|당일치기|당일|\d{1,2}\s*일\s*(?:간|동안|일정|여행|코스)|\d{1,2}\s*주(?:일)?\s*(?:간|동안)?|일주일|한\s*달|이틀|사흘|나흘|닷새|엿새|이레|열흘|보름", " ", work)
    work = re.sub(r"쯤으로|쯤|(?:여행을?\s*)?(?:갈\s*)?예정(?:이야|이에요|입니다|이라)?", " ", work)  # 날짜 뒤에 남는 군말은 취향이 아니다
    # 축제를 찾아 달라는 말·일정이 빈 날을 말한 것은 취향이 아니라 요청이다 ("두번째 날에 일정이 좀 비어 그래서 괜찮은 축제 있나 한번 찾아주고")
    work = re.sub(r"(?:괜찮은|좋은|볼\s*만한|볼만한)?\s*(?:축제|행사|공연|페스티벌|이벤트)(?:가|는|도|를|을)?\s*(?:있나|있을까|있어|있니|없나)?\s*(?:한번|한\s*번|좀)?\s*"
                  r"(?:찾아|추천|알려|보여)\w*", " ", work)
    work = re.sub(r"(?:첫|둘|셋|넷|두|세|네|\d{1,2})\s*(?:번\s*)?째\s*날(?:에는|에|엔)?|\d{1,2}\s*일\s*차(?:에는|에|엔)?", " ", work)
    work = re.sub(r"일정이\s*(?:좀\s*)?(?:비어|비는|남아|비네|부족해|허전해)\w*|가는데|갈\s*건데|가려고\w*|(?<![가-힣])(?:그래서|그리고|그런데|근데|한번|한\s*번)(?![가-힣])", " ", work)
    work = re.sub(r"(?<![가-힣])(?:내가|제가|저는|나는|우리가?|저희가?)(?![가-힣])", " ", work)
    work = re.sub(r"(?<![가-힣])(?:여행|일정)(?:을|를|이|은|는|인데|이야|이고|이에요|이라|인데요)?(?![가-힣])", " ", work)   # "2박 3일 여행인데" 의 군말
    work = re.sub(r"(?<![가-힣])(?:에|은|는|이|가|을|를|도|로|으로|에서)(?![가-힣])", " ", work)          # 지역·날짜를 지운 자리에 남은 조사
    work = re.sub(r"[\s.]+", " ", work).strip()
    return re.sub(r"^(?:에서|에|부터|까지|으로|로)\s+", "", work)  # "주말에 바다" → "바다 …" (날짜를 지우고 남은 조사)


def _heuristic_party(text: str) -> str:
    for label, pat in PARTY_PATTERNS:
        if re.search(pat, text):
            return label
    return ""


def _history_text(session: ChatSession, n: int = 4) -> str:
    msgs = session.history[-(n + 1):-1]  # 방금 들어온 사용자 메시지는 제외
    return "\n".join(f"{'사용자' if m['role'] == 'user' else '챗봇'}: {_clip(m['content'], 150)}" for m in msgs) or "(없음)"


def _llm_extract(session: ChatSession, text: str, today: date, warnings: list[str]) -> dict | None:
    s = session.slots
    known = {k: s[k] for k in ("region", "area", "start_date", "end_date", "party", "preferences", "avoid")}
    user = (
        f"오늘 날짜: {today.isoformat()}({WD[today.weekday()]}요일)\n"
        f"현재까지 파악된 정보: {json.dumps(known, ensure_ascii=False)}\n"
        f"최근 대화:\n{_history_text(session)}\n"
        f"최신 메시지: {text}"
    )
    try:
        parsed, _ = _llm_json(
            [{"role": "system", "content": EXTRACT_SYSTEM}, {"role": "user", "content": user}], temperature=0.0
        )
    except Exception as e:
        warnings.append(f"AI 연결 문제로 간단한 규칙으로 이해했어요 ({type(e).__name__}: {str(e)[:500]})")
        return None
    return parsed if isinstance(parsed, dict) else None


def _trip_key(slots: dict) -> tuple:
    return (slots["region"], slots["area"], slots["start_date"], slots["end_date"])


def _apply_extraction(session: ChatSession, text: str, llm: dict | None, today: date, in_plan: bool,
                      skipped: bool = False) -> list[str]:
    """추출 결과를 슬롯에 반영하고, 사용자에게 알려야 할 문제(issue 코드)를 돌려줍니다."""
    s, issues = session.slots, []
    llm_ok = llm is not None
    llm = llm or {}
    # ── 지역 ──
    sido, area = resolve_place_ext(text)
    ambiguous = [] if sido else ambiguous_regions(text)
    if sido and not area and len(text) <= 12:
        # "고성은 강원·경남 중 어디예요?"에 "강원"이라고만 답한 경우: 앞 메시지의 이름을 그 시도에서 찾는다
        prev = _prev_user_text(session)
        if any(sido in sidos for _, sidos in ambiguous_regions(prev)):
            area = lookup_in_sido(prev, sido)
    # 일정이 나온 뒤에는 '바꿔줘/갈래' 같은 변경 의도가 있거나 '이전과 다른 새 지역'을 말했을 때만 지역·날짜를 바꾼다
    # (예: "내일 비 와?"라고 물었다고 출발일이 바뀌면 안 되지만, 새 지역을 말하면 이전 지역 데이터는 버린다)
    explicit_new_region = bool(sido) and (sido != s["region"] or bool(area and area != s["area"]))
    allow_change = (not in_plan) or bool(CHANGE_RE.search(text)) or explicit_new_region
    if ambiguous and allow_change:
        issues.append("ambiguous_region")  # AI가 한쪽을 짐작하지 않게 되묻는다
    elif not sido and _province_group(text) and allow_change:
        issues.append("province_group")  # '전라도'처럼 시도 여러 개를 묶은 이름: 어느 시도·도시인지 되묻는다
    elif not sido:
        lr, la = str(llm.get("region") or "").strip(), str(llm.get("area") or "").strip()
        in_text = [t for t in (lr, la) if t and t in text]
        if in_text:  # 사용자가 실제로 말한 지명일 때만 LLM 결과를 신뢰 (지어낸 지역 방지)
            cand, _ = resolve_place(f"{lr} {la}")
            if cand:
                sido, area = cand, (la if la and la in text else "")
            elif allow_change:
                issues.append("unknown_region")
    if sido and allow_change:
        if sido != s["region"]:
            s["area"] = ""
        s["region"] = sido
        if area:
            s["area"] = area

    # ── 날짜 ──
    if allow_change:
        rd = parse_trip_dates(text, today)
        s_new, e_new, n_new = rd["start"], rd["end"], rd["nights"]
        hint = s.get("date_hint") or {}
        if rd.get("rough", {}) and rd["rough"].get("past") and not s_new:
            issues.append("past_date")  # '저번 주', '지난달'만 말함 → 이미 지난 때
        elif rd.get("rough") and not s_new:
            s["date_hint"] = hint = rd["rough"]  # '다음달', '다다음주'만 말함 → 며칠·무슨 요일인지 되묻는다
        elif hint and not s["start_date"] and not re.search(r"\d\s*월|이번|다음|주\s*말|오늘|내일|모레|글피", text):
            plain = re.sub(r"\d{1,2}\s*박\s*\d{1,2}\s*일", " ", text)  # "2박3일"의 "3일"은 날짜가 아님
            dm = re.search(r"(?<!\d)(\d{1,2})\s*일(?!\s*(?:차|째|간|동안|일정|여행))", plain)
            one = re.fullmatch(r"\s*([월화수목금토일])\s*", text)
            if "month" in hint and dm:
                # "12월" → "5일(부터)" = 12월 5일
                first = date_in_month(hint["month"], int(dm.group(1)), today)
                if first:
                    if s_new and e_new:
                        e_new = first + (e_new - s_new)
                    s_new = first
                    if not re.search(r"\d+\s*박|당일", text):
                        n_new = None
            elif "week" in hint and one:
                s_new = parse_iso(hint["week"]) + timedelta(days=WD.index(one.group(1)))  # "토" 한 글자 답
            elif "week" in hint and s_new:
                # "다음주" → "금요일" = 그 주 금요일
                shift = (parse_iso(hint["week"]) + timedelta(days=s_new.weekday())) - s_new
                s_new, e_new = s_new + shift, (e_new + shift if e_new else None)
        if rd.get("bare_day") and s["nights"] is not None and not s["start_date"] and not s_new and not re.search(r"\d+\s*박", text):
            # 기간은 이미 알고 출발일을 묻는 중에 "20일"이라고 답하면 기간이 아니라 날짜
            s_new, n_new = day_of_month(rd["bare_day"], today), None
        if not (s_new or e_new) and DATE_HINT_RE.search(text):
            ls, le = parse_iso(llm.get("start_date")), parse_iso(llm.get("end_date"))
            if ls and ls >= today:  # LLM이 계산한 과거 날짜는 환각일 가능성이 커서 무시
                s_new, e_new = ls, le
        old_s, old_e = parse_iso(s["start_date"]), parse_iso(s["end_date"])
        if n_new is not None:
            s["nights"] = n_new
        start, end = old_s, old_e
        if s_new:
            start = s_new
            if e_new and not (rd.get("end_implied") and s["nights"] is not None):
                # '주말'로 짐작한 끝 날짜보다, 앞에서 말한 기간("창원 4박 5일" → "이번 주말")이 우선
                end = e_new
            elif n_new is not None:
                end = start + timedelta(days=n_new)
            elif s["nights"] is not None:
                end = start + timedelta(days=s["nights"])
            elif old_s and old_e:
                end = start + (old_e - old_s)  # 출발일만 옮기면 기간은 유지
            else:
                end = None
        elif e_new:
            end = e_new
        elif n_new is not None and start:
            end = start + timedelta(days=n_new)

        if start and start < today:
            issues.append("past_date")
            start, end = old_s, old_e
        if start and end and end < start:
            issues.append("bad_range")
            end = None
        if start and end and (end - start).days + 1 > MAX_TRIP_DAYS:
            issues.append("too_long")
            end = None
        s["start_date"] = start.isoformat() if start else ""
        s["end_date"] = end.isoformat() if end else ""
        if start:
            s["date_hint"] = None
        if start and end:
            s["nights"] = (end - start).days

    # ── 동행 · 취향 · 피할 것 ──
    party = str(llm.get("party") or "").strip()
    if not party or EMPTY_ANSWER_RE.match(party):
        party = _heuristic_party(text)
    if party:
        s["party"] = party[:30]
    s["preferences"] = _merge_text(s["preferences"], str(llm.get("preferences") or ""))
    s["avoid"] = _merge_text(s["avoid"], str(llm.get("avoid") or ""))
    if not llm_ok and not RESET_RE.search(text) and (not skipped or not in_plan):
        # AI 없이 처리한 경우(실패했거나 일부러 건너뜀): 지역·날짜를 뺀 나머지 말을 취향으로 사용.
        # 수정 요청(in_plan)에서 건너뛴 경우는 일정 수정 호출이 요청을 직접 해석하므로 넣지 않는다.
        extra = _leftover(text, today)
        if len(extra) >= 6:
            s["preferences"] = _merge_text(s["preferences"], _clip(extra, 60))
    return issues


# ── 되묻기 ────────────────────────────────────────────────────────────
def _missing(s: dict) -> list[str]:
    return [k for k in ("region", "start_date", "end_date") if not s[k]]


def _label(s: dict) -> str:
    if s["area"] == s["region"]:  # "제주 제주" → "제주"
        return s["region"]
    return f"{s['region']} {s['area']}".strip()


def _date_phrase(s: dict) -> str:
    start, end = parse_iso(s["start_date"]), parse_iso(s["end_date"])
    if start and end and start != end:
        return f"{fmt_korean(start)} ~ {fmt_korean(end)}"
    if start and end:
        return f"{fmt_korean(start)} 당일"
    if start:
        return f"{fmt_korean(start)} 출발"
    if s["nights"] is not None:
        return "당일치기" if s["nights"] == 0 else f"{s['nights']}박 {s['nights'] + 1}일"
    return ""


def _ask_missing(s: dict) -> str:
    if not s["region"]:
        known = _date_phrase(s)
        if known:
            return f"{known} 일정으로 이해했어요. 어느 지역으로 가실 건가요? (예: 부산, 제주, 강릉)"
        return "어디로 떠나고 싶으세요? 지역(예: 부산, 제주, 강릉)과 날짜를 알려주세요 😊"
    if not s["start_date"]:
        extra = f"{_date_phrase(s)} 일정이군요. " if s["nights"] is not None else ""
        hint = s.get("date_hint") or {}
        if "month" in hint:
            m = hint["month"]
            return f"{_label(s)} 좋아요! {extra}{m}월 며칠에 출발하실까요? (예: {m}월 5일, 20일부터)"
        if "week" in hint:
            mon = parse_iso(hint["week"])
            return (f"{_label(s)} 좋아요! {extra}{fmt_md(mon)}~{fmt_md(mon + timedelta(days=6))} 주의 무슨 요일에 출발하실까요? "
                    "(예: 금요일, 토일)")
        return f"{_label(s)} 좋아요! {extra}언제 출발하시나요? (예: 10월 10일, 이번 주말, 내일)"
    return f"{_label(s)}, {_date_phrase(s)}이군요. 몇 박 며칠로 다녀오실 예정인가요? (예: 2박 3일, 당일치기)"


def _ask_optional(s: dict, stay_line: str = "") -> str:
    return (
        f"{_label(s)}, {_date_phrase(s)} 일정이네요! 더 잘 맞는 일정을 짜드리려고 하나만 여쭤볼게요.\n"
        "누구와 함께 가시나요? 그리고 원하는 분위기(예: 조용한 바다, 맛집 위주, 사진 명소, 아이와 함께)가 있으면 알려주세요.\n"
        + (stay_line + "\n" if stay_line else "")
        + "특별한 건 없으면 \"상관없어요\"라고 해주세요."
    )


# 앱의 권역 이름(새 여행 화면)처럼 시도 여러 개를 묶은 말 → (시도들, 예시 도시)
PROVINCE_GROUPS = {
    "전라도": (["전북", "전남", "광주"], "전주, 여수, 순천, 목포, 광주"),
    "경상도": (["경북", "경남", "부산", "대구", "울산"], "경주, 안동, 창원, 통영, 부산"),
    "충청도": (["충북", "충남", "대전", "세종"], "청주, 단양, 공주, 태안, 대전"),
}
_GROUP_RE = re.compile(r"(전라|경상|충청)\s*도")


def _province_group(text: str) -> str:
    """'전라도'처럼 시도 여러 개를 묶은 이름이 있으면 그 이름 ('전라남도'처럼 한 시도를 말한 것은 아님)."""
    m = _GROUP_RE.search(text or "")
    return f"{m.group(1)}도" if m else ""


def _province_group_question(text: str) -> str:
    name = _province_group(text)
    if not name:
        return ""
    sidos, examples = PROVINCE_GROUPS[name]
    return f"{name}는 {'·'.join(sidos)}로 나뉘어 있어서 한 곳을 정해야 일정을 짤 수 있어요. 어느 도시로 가실 건가요? (예: {examples})"


def _issue_message(issues: list[str], today: date, text: str = "") -> str:
    amb = ambiguous_regions(text) if "ambiguous_region" in issues else []
    msgs = {
        "ambiguous_region": "\n".join(
            f"'{name}'은(는) {', '.join(sidos)}에 모두 있어요. 어느 쪽인가요? (예: {sidos[0]} {name})" for name, sidos in amb),
        "past_date": f"말씀하신 날짜가 이미 지났어요. 오늘({fmt_korean(today)}) 이후 날짜로 다시 알려주시겠어요?",
        "bad_range": "도착일이 출발일보다 빠르네요. 날짜를 다시 알려주시겠어요?",
        "too_long": f"한 번에 최대 {MAX_TRIP_DAYS}일까지 일정을 짜드릴 수 있어요. 기간을 줄여서 다시 알려주시겠어요?",
        "unknown_region": "아직 지원하지 않는 지역이에요. 가능한 지역: " + ", ".join(SIDO),
        "province_group": _province_group_question(text),
    }
    return "\n".join(msgs[i] for i in dict.fromkeys(issues) if i in msgs)


# ── 일정 생성 ─────────────────────────────────────────────────────────
def _history_for_llm(session: ChatSession) -> list[dict]:
    msgs = session.history[:-1][-(CHAT_HISTORY_TURNS * 2):]  # 현재 요청은 마지막 user 메시지로 따로 보냄
    return [{"role": m["role"], "content": _clip(m["content"], 300 if m["role"] == "assistant" else 500)} for m in msgs]


def _cand_line(cid: str, p: dict, news_by_id: dict) -> str:
    c = _coord(p)
    where = " ".join(x for x in [district_of(p["addr"]), f"({c[0]:.3f},{c[1]:.3f})" if c else ""] if x) or "위치 정보 없음"
    line = f"{cid} | {p['content_type']} | {'실내' if p.get('indoor') else '실외'} | {p['title']} | {where} | 주소: {p['addr'] or '정보없음'}"
    if p.get("overview"):
        line += f" | 소개: {p['overview'][:120]}"
    if p.get("event_start"):
        line += f" | 행사기간: {p['event_start']}~{p['event_end']}"
    related = [n for n in p.get("related_news_ids", []) if n in news_by_id]
    if related:
        line += " | 관련이슈: " + "; ".join(f"{n} {news_by_id[n]['title'][:40]}" for n in related[:2])
    return line


def _plan_text(plan: dict, cand_map: dict, dates: list[str]) -> str:
    lines = []
    for date_, day in zip(dates, plan["days"]):
        parts = []
        for it in day["items"]:
            p = cand_map.get(it["candidate_id"]) if it["candidate_id"] else None
            parts.append(f"{it['slot']} {it['candidate_id']}({p['title']})" if p else f"{it['slot']} {it['note'] or '자유'}")
        lines.append(f"- {date_}" + (f" [{day['theme']}]" if day["theme"] else "") + ": " + ", ".join(parts))
    return "\n".join(lines)


def _caveats(raw: dict, conditions: list[dict], extra: list[str], start: date, end: date, today: date) -> list[str]:
    out = list(raw["warnings"]) + extra
    out.append(f"뉴스 이슈는 최근 {NEWS_DAYS_BACK}일 기사 기준이라 여행일이 멀면 상황이 달라질 수 있어요.")
    no_weather = [c["label"] for c in conditions if not c["weather"]]
    no_air = [c["label"] for c in conditions if not c["air"]]
    if no_weather:
        out.append(f"날씨 예보는 오늘부터 약 {FORECAST_DAYS}일까지만 제공돼 {', '.join(no_weather)}은 반영하지 못했어요.")
    if no_air:
        out.append(f"미세먼지 예보는 오늘~모레만 제공돼 {', '.join(no_air)}은 반영하지 못했어요.")
    if any(c["weather"] for c in conditions):
        out.append(f"날씨는 {SIDO[raw['sido']]['city']} 기준 예보라 세부 지역과 다를 수 있어요.")
    out.append("실내/실외 구분은 장소 이름과 유형으로 추정한 값이라 실제와 다를 수 있어요.")
    out.append("관광정보는 한국관광공사 TourAPI 기준이며 운영시간·휴무는 방문 전에 확인해 주세요.")
    return list(dict.fromkeys(out))


def _expand_nearby(raw: dict, sido: str, area: str, start: date, end: date) -> None:
    """
    시·군 안의 장소만으로 일정이 모자랄 때, 같은 시도 전체 장소 중 그 지역에서 가까운 순으로 덧붙인다 (nearby=True).
    raw(세션 캐시)에 바로 넣고 expanded 표시를 해서 같은 여행 조건에서는 다시 부르지 않는다.
    """
    raw["expanded"] = True
    try:
        extra, w = _collect_candidates(sido, start, end, True, "")
    except Exception as e:
        raw["warnings"].append(f"주변 장소 보충 실패: {type(e).__name__}")
        return
    have = {(p["content_id"] or p["title"]) for p in raw["places"]}
    coords = [c for c in (_coord(p) for p in raw["places"]) if c]
    if not coords:
        return
    center = {"mapy": sum(c[0] for c in coords) / len(coords), "mapx": sum(c[1] for c in coords) / len(coords)}
    added = []
    for p in extra:
        if (p["content_id"] or p["title"]) in have or not _coord(p):
            continue
        p["nearby"] = True
        added.append(p)
    added.sort(key=lambda p: straight_km(center, p) or 1e9)
    raw["places"] += added
    raw["warnings"] += w[:2]
    if added:
        raw["warnings"].append(f"'{area}' 안의 장소만으로는 긴 일정을 채우기 어려워 가까운 {sido} 지역 장소 {len(added)}곳을 함께 후보로 썼어요.")


# "저거 기준으로", "그 축제로"처럼 방금 보여준 축제 목록을 가리키는 말 / 축제를 빼달라는 말
FEST_REF_RE = re.compile(r"저거|그거|이거|그것|이것|위에|위의|방금|아까|그\s*축제|그\s*행사|기준|맞춰")
FEST_DROP_RE = re.compile(r"빼|제외|없이|말고|싫")


_GENERIC_FEST_WORDS = {"축제기간", "축제위주", "행사기간", "축제중심", "페스티벌", "여행일정", "일정짜줘"}


def _fest_core(title: str) -> str:
    """축제 이름에서 연도·회차·괄호를 뺀 핵심 이름 ('2026 부산불꽃축제(제20회)' → '부산불꽃축제')"""
    return re.sub(r"[\W_]+", "", re.sub(r"\(.*?\)|\[.*?\]|\d{4}|제\s*\d+\s*회", "", title or ""))


def _names_festival(text: str, title: str) -> bool:
    """사용자가 말에서 이 축제를 이름으로 가리켰는가 ('부산불꽃축제 위주로', '불꽃축제 저녁 7시')"""
    core = _fest_core(title)
    if not core:
        return False
    if core in re.sub(r"[\W_]+", "", text or ""):
        return True
    toks = [t for t in re.findall(r"[가-힣A-Za-z0-9]{4,}", text or "") if t not in _GENERIC_FEST_WORDS]
    return any(t in core for t in toks)


def _festival_pins(session: "ChatSession", text: str, raw: dict, dates: list[str]) -> dict[int, dict]:
    """
    일정에 꼭 넣을 축제 {일차 순번: 축제}. 축제를 말했거나("축제 방문 기준으로 짜줘") 방금 보여준 축제 목록을
    가리키면("저거 기준으로 다시 짜줘") 여행 기간과 겹치는 축제를 그 축제가 열리는 날에 하루 하나씩 배치한다.
    """
    # '저거/기준' 같은 말은 바로 앞 답변이 축제 목록일 때만 축제를 가리킨다 ("실내 기준으로 바꿔줘"와 구분)
    refers = bool(session.last_festivals) and bool(FEST_REF_RE.search(text)) and "축제·행사" in _prev_assistant_text(session)
    if FEST_DROP_RE.search(text) or not (FEST_RE.search(text) or refers):
        return {}
    area = session.slots["area"]
    shown = [p for p in session.last_festivals if not area or area in p["addr"] or area in p["title"]]
    pool = shown or [p for p in raw["places"] if str(p.get("content_type_id")) == "15"]
    named = [p for p in pool if _names_festival(text, p["title"])]
    if not (named or refers or FEST_FOCUS_RE.search(text)):
        return {}  # "축제 있나 찾아줘"처럼 추천만 부탁했다: 일정에 마음대로 넣지 않는다
    if named:  # 축제 이름을 콕 집어 말했으면 그 축제만 ("부산불꽃축제 위주로 짜줘")
        pool = named
    days = [d.replace("-", "") for d in dates]
    pins: dict[int, dict] = {}
    for p in sorted(pool, key=lambda p: p.get("event_end") or p.get("event_start") or "99999999"):  # 일찍 끝나는 축제부터
        fs = p.get("event_start") or ""
        fe = p.get("event_end") or fs
        free = [i for i, d in enumerate(days) if (not fs or fs <= d) and (not fe or d <= fe) and i not in pins]
        if free:
            pins[free[0]] = p
    return pins


def _apply_pins(days: list[dict], pin_cids: dict[int, str]) -> None:
    """축제를 정해진 날로 옮겨 넣는다 (다른 날에 있으면 빼고). 하루 5곳을 넘으면 뒤쪽 일반 장소를 뺀다."""
    pinned = set(pin_cids.values())
    for d in days:
        d["items"] = [it for it in d["items"] if it["candidate_id"] not in pinned]
    for i, cid in pin_cids.items():
        items = days[i]["items"]
        items.insert(min(1, len(items)), {"slot": "", "candidate_id": cid, "note": "축제 기간에 맞춰 넣었어요."})
        while sum(1 for it in items if it["candidate_id"]) > 5:
            j = next((j for j in range(len(items) - 1, -1, -1) if items[j]["candidate_id"] not in pinned), None)
            if j is None:
                break
            items.pop(j)


FEST_AREA_KM = 12  # 축제가 있는 날, 다른 방문지는 축제장에서 이 거리(직선) 안에서 고른다
LODGING_AREA_KM = 6  # 숙소를 알려줬을 때, 다른 방문지는 숙소에서 이 거리(직선) 안에서 고른다


def _gather_around_festivals(days: list[dict], pin_cids: dict[int, str], cand_map: dict, sights: list[dict], cid_of,
                             conditions: list[dict], want: int = 4, keep_cids: set | None = None,
                             radius: float = FEST_AREA_KM, centers: dict[int, dict] | None = None) -> None:
    """
    축제(또는 사용자가 고른 장소)가 있는 날은 나머지 방문지를 그 주변으로 모은다: 멀리 있는 장소는 빼고, 가까운 장소(아직 안 쓴 것)로 채운다.
    궂은 날은 실내 장소를 먼저. 좌표가 없는 중심 장소는 건드리지 않는다. keep_cids: 멀어도 빼지 않을 장소(사용자가 고른 것 등).
    centers: {일차: 중심 장소} 를 직접 줄 때 (숙소처럼 일정 후보가 아닌 곳). 이때 pin_cids 의 값은 쓰지 않는다. radius: 중심에서 이 거리(km) 안.
    """
    pinned = set(pin_cids.values()) | (keep_cids or set())
    for i, fcid in pin_cids.items():
        fest = centers[i] if centers else cand_map[fcid]
        if _coord(fest) is None:
            continue
        day = days[i]
        keep, far = [], []
        for it in day["items"]:
            cid = it["candidate_id"]
            p = cand_map.get(cid) if cid else None
            if cid in pinned or p is None or (straight_km(fest, p) or 0) <= radius:
                keep.append(it)
            else:
                far.append((straight_km(fest, p), it))
        day["items"] = keep
        used = {(cand_map[it["candidate_id"]].get("content_id") or cand_map[it["candidate_id"]].get("title"))
                for d in days for it in d["items"] if it["candidate_id"] in cand_map}
        bad = conditions[i].get("outdoor_ok") is False
        near, anywhere = [], []
        for p in sights:
            if str(p.get("content_type_id")) == "15" or (p.get("content_id") or p.get("title")) in used:
                continue
            d = straight_km(fest, p)
            if d is None:
                continue
            (near if d <= radius else anywhere).append((bool(p.get("indoor")) != bad, d, p))
        near.sort(key=lambda x: (x[0], x[1]))
        anywhere.sort(key=lambda x: x[1])

        def others() -> int:
            return sum(1 for it in day["items"] if it["candidate_id"] and it["candidate_id"] not in pinned)

        def add(p: dict) -> None:
            cid = cid_of(p)
            cand_map[cid] = p
            day["items"].append({"slot": "", "candidate_id": cid, "note": ""})

        for _, _, p in near:
            if others() >= want:
                break
            add(p)
        # 주변에 장소가 모자라 하루가 비면: 빼려던 먼 장소를 가까운 순으로 되살리고, 그래도 모자라면 전체에서 가까운 순으로 채운다
        for _, it in sorted(far, key=lambda x: x[0] or 0):
            if others() >= 3:
                break
            day["items"].append(it)
        for _, _, p in anywhere:
            if others() >= 3:
                break
            add(p)


def _sync_festivals(session: ChatSession, plan: dict, cand_map: dict) -> None:
    """지금 일정에 들어 있는 축제를 기록한다 (시간 안내·시간 입력용). 일정에서 빠진 축제의 시간은 버린다."""
    found: dict[str, dict] = {}
    for di, day in enumerate(plan["days"]):
        for it in day["items"]:
            p = cand_map.get(it["candidate_id"]) if it["candidate_id"] else None
            if p and str(p.get("content_type_id")) == "15":
                key = p.get("content_id") or p.get("title")
                if key not in found:
                    old = session.fest_pins.get(key, {})
                    found[key] = {"title": p["title"], "day": di, "start": p.get("event_start") or "", "end": p.get("event_end") or "",
                                  "asked": bool(old.get("asked"))}
    session.fest_pins = found
    session.fest_times = {k: v for k, v in session.fest_times.items() if k in found}
    session.awaiting_fest_time = any(k not in session.fest_times for k in found)


def _fixed_map(session: ChatSession) -> dict:
    """시각이 정해진 장소 {장소 key: (시작 분, 끝 분 또는 None)}: 사용자가 알려준 축제 시간 + 시간을 말한 장소"""
    fixed = dict(session.fest_times)
    for e in session.user_places:
        if e.get("time"):
            fixed[key_of(e["place"])] = e["time"]
    return fixed


def _lodging_for(session: ChatSession) -> dict | None:
    """지금 여행 시도 안에 있는 숙소만 쓴다 (지역을 바꿨는데 이전 지역 숙소에서 출발하는 일정이 나오지 않게)."""
    lo = session.lodging
    if lo is None:
        return None
    ok = _region_matcher(session.slots)
    return lo if (ok is None or ok(lo.get("addr", ""))) else None


def _cid(session: ChatSession, p: dict) -> str:
    k = p["content_id"] or p["title"]
    if k not in session.id_map:
        session.id_map[k] = f"C{len(session.id_map) + 1}"
    return session.id_map[k]


def _apply_user_places(session: ChatSession, days: list[dict], cand_map: dict, cid_of, conditions: list[dict], sights: list[dict],
                       festival_days: set[int] = frozenset()) -> None:
    """사용자가 말한 장소를 일정에 넣고, 그 날의 나머지는 그 장소들 주변에서 채운다. 몇 번을 불러도 같은 결과(이미 있으면 빼고 다시 넣음)."""
    s = session.slots
    ctx = (s["region"], s["area"])
    entries = [e for e in session.user_places if e.get("ctx") in (None, ctx)]  # 다른 지역으로 바꿨다면 이전 지역 장소는 쓰지 않는다
    n = len(days)
    mine: set[str] = set()
    centers: dict[int, str] = {}
    if entries:
        for e in entries:
            ref = e.get("day_ref")
            e["day"] = n - 1 if ref == -1 else (ref - 1 if ref and 1 <= ref <= n else None)
        integrate(entries, days, cand_map, cid_of)
        mine = {cid_of(e["place"]) for e in entries}
    festival_cids = {it["candidate_id"] for d in days for it in d["items"] if it["candidate_id"] in cand_map
                     and str(cand_map[it["candidate_id"]].get("content_type_id")) == "15"}
    if entries:
        for e in sorted(entries, key=lambda e: (e["time"] is None, e["time"] or (0, 0))):  # 시간이 정해진 장소를 그날의 중심으로
            if e.get("assigned_day") is not None and e["assigned_day"] not in festival_days:
                centers.setdefault(e["assigned_day"], cid_of(e["place"]))
        if centers:
            _gather_around_festivals(days, centers, cand_map, sights, cid_of, conditions, keep_cids=mine | festival_cids)
    # 숙소가 있으면, 위에서 중심이 정해지지 않은 날은 숙소 주변에서 고른다 (숙소 기준 동선을 부탁받은 경우)
    lodging = _lodging_for(session)
    if lodging is not None:
        stay_days = {i: "LODGING" for i in range(n) if i not in centers and i not in festival_days}
        _gather_around_festivals(days, stay_days, cand_map, sights, cid_of, conditions, keep_cids=mine | festival_cids,
                                 radius=LODGING_AREA_KM, centers={i: lodging for i in stay_days})


def _open_on(p: dict, ymd: str) -> bool:
    """축제가 이 날(YYYYMMDD)에 열리는가 (기간을 모르면 열린다고 본다)"""
    fs = p.get("event_start") or ""
    fe = p.get("event_end") or fs
    return (not fs or fs <= ymd) and (not fe or ymd <= fe)


def _festival_offer(session: ChatSession, ranker, dates: list[str], hint_day: int | None, sido: str, area: str, query: str,
                    start: date, end: date) -> tuple[str, list[str]]:
    """
    여행 기간에 열리는 축제를 추천한다 (일정에는 넣지 않는다). 사용자가 "1번 2일차에 추가해줘"라고 하면 _try_festival_add 가 넣는다.
    비어 있다고 말한 날(hint_day)에 열리는 축제를 먼저 보여준다.
    """
    places, warns = _collect_festivals(sido, area, start, end)
    pool = [p for p in places if str(p.get("content_type_id")) == "15"]
    span = f"{fmt_md(start)} ~ {fmt_md(end)}" if end != start else fmt_md(start)
    if not pool:
        session.last_festivals = []
        return f"🎉 **{area or sido} 여행 기간({span})에 열리는 축제·행사를 찾지 못했어요.** 그 대신 위 일정으로 즐겨 보세요.", warns
    ranked = rank_places(pool, sido, query, ranker)
    day_ymd = dates[hint_day].replace("-", "") if hint_day is not None and 0 <= hint_day < len(dates) else None
    if day_ymd:
        ranked = sorted(ranked, key=lambda p: not _open_on(p, day_ymd))  # 그 날 열리는 축제를 앞으로 (순위는 그대로)
    items = ranked[:5]
    warns += enrich(items)
    session.last_festivals = items
    lines = [f"## 🎉 {area or sido} {span} 축제·행사 추천", ""]
    if day_ymd:
        lines += [f"{hint_day + 1}일차({_md(dates[hint_day].replace('-', ''))})가 비어 있다고 하셔서, 그날 열리는 축제를 먼저 골랐어요.", ""]
    for i, p in enumerate(items, 1):
        on = [str(k + 1) for k, d in enumerate(dates) if _open_on(p, d.replace("-", ""))]
        period = _period(p)
        lines.append(f"**{i}. {p['title']}**")
        lines.append(f"- 🗓 기간: {period} (여행 중 {', '.join(on)}일차에 열려요)")
        if p.get("addr"):
            lines.append(f"- 📍 위치: {p['addr']}")
        feature = one_liner(p.get("overview", ""), 90)
        if feature:
            lines.append(f"- 💡 특징: {feature}")
        lines.append("")
    lines.append('마음에 드는 축제가 있으면 "1번 2일차에 추가해줘"처럼 말씀해 주세요. 추가하면 그날 나머지 일정을 축제장 주변으로 다시 맞춰 드려요.')
    return "\n".join(lines), warns


def _fest_choice(session: ChatSession, text: str) -> dict | None:
    """추천받은 축제 중 사용자가 가리킨 하나: 이름("불꽃축제"), 번호("1번", "두 번째"), 하나뿐일 때의 "이거"."""
    offered = session.last_festivals
    named = [p for p in offered if _names_festival(text, p["title"])]
    if len(named) == 1:
        return named[0]
    if "축제·행사" not in _prev_assistant_text(session):
        return None  # 번호·'이거'는 바로 앞 답변이 축제 추천일 때만 축제를 가리킨다 (맛집 목록의 "1번"과 구분)
    ordinal = {"첫": 1, "두": 2, "세": 3, "네": 4, "다섯": 5}
    m = re.search(r"(\d)\s*번", text) or re.search(r"(첫|두|세|네|다섯)\s*(?:번)?\s*째", text)
    if m:
        k = int(m.group(1)) if m.group(1).isdigit() else ordinal[m.group(1)]
        return offered[k - 1] if 1 <= k <= len(offered) else None
    if len(offered) == 1 and re.search(r"이거|이걸|그거|그걸|저거|저걸|이\s*축제|그\s*축제", text):
        return offered[0]
    return None


def _try_festival_add(session: ChatSession, text: str) -> dict | None:
    """
    추천받은 축제를 일정에 넣는다. "1번 2일차에 추가해줘" → 바로 추가, "1번 괜찮네요" → "추가할까요?" 하고 "네"에 추가.
    추가하면 그날 나머지 장소는 축제장 주변으로 다시 모으고, 축제 시간을 모르니 알려 달라고 안내한다. 해당 없으면 None.
    """
    pending, session.fest_pending = session.fest_pending, None  # 어떤 말이든 한 번 지나면 '추가할까요?' 대기는 끝
    if not (session.plan and session.view and session.last_festivals and session.slots["start_date"]):
        return None
    pick = _fest_choice(session, text)
    wants_add, likes = bool(FEST_ADD_RE.search(text)), bool(FEST_POS_RE.search(text))
    after_offer = "축제·행사" in _prev_assistant_text(session)
    if pick is None and pending is not None and FEST_YES_RE.search(text):
        pick = pending  # "추가할까요?"에 "네"
        wants_add = True
    if pick is None:
        if after_offer and (wants_add or likes) and len(session.last_festivals) > 1 and not FEST_RE.search(text) and not MODIFY_RE.search(re.sub(r"추가|넣어", "", text)):
            reply = f"어느 축제를 말씀하시나요? 번호(1~{len(session.last_festivals)})나 이름으로 알려주세요."
            session.history.append({"role": "assistant", "content": reply})
            return _pack(session, "planned", reply)
        return None
    if not (wants_add or likes):
        return None  # 축제 이름만 언급 (시간 지정 등은 다른 처리가 맡는다)

    dates = [(parse_iso(session.slots["start_date"]) + timedelta(days=i)).isoformat()
             for i in range((parse_iso(session.slots["end_date"]) - parse_iso(session.slots["start_date"])).days + 1)]
    n = len(dates)
    open_days = [i for i, d in enumerate(dates) if _open_on(pick, d.replace("-", ""))]
    period = _period(pick)
    if not open_days:
        reply = f"**{pick['title']}** 은(는) 여행 기간에 열리지 않아요 (개최 {period}). 다른 축제를 골라 주세요."
        session.history.append({"role": "assistant", "content": reply})
        return _pack(session, "planned", reply)
    wanted = _target_days(text, n)
    if wanted and wanted[0] not in open_days:
        ok = ", ".join(f"{i + 1}일차" for i in open_days)
        reply = f"**{pick['title']}** 은(는) {wanted[0] + 1}일차에는 열리지 않아요 (개최 {period}). {ok}에는 넣을 수 있어요."
        session.history.append({"role": "assistant", "content": reply})
        return _pack(session, "planned", reply)
    visits = [sum(1 for it in d["items"] if it["candidate_id"]) for d in session.plan["days"]]
    if wanted:
        day = wanted[0]
    elif session.fest_hint_day in open_days:
        day = session.fest_hint_day
    else:
        day = min(open_days, key=lambda i: (visits[i], i))  # 열리는 날 중 일정이 가장 한가한 날
    if not wants_add:  # 마음에 든다고만 했다: 넣을지 확인
        session.fest_pending = pick
        session.fest_hint_day = day if wanted else session.fest_hint_day
        reply = (f"**{pick['title']}** 을(를) {day + 1}일차({_md(dates[day].replace('-', ''))})에 넣을까요? "
                 f"\"네\" 또는 \"추가해줘\"라고 하시면 넣고, 그날 시간표를 다시 맞춰 드려요.")
        session.history.append({"role": "assistant", "content": reply})
        return _pack(session, "planned", reply)

    plan, cand_map = session.plan, session.last_cand_map
    cid_of = lambda p: _cid(session, p)
    cid = cid_of(pick)
    cand_map[cid] = pick
    sights = [p for p in (session.raw or {}).get("places", []) if p["content_type_id"] in SIGHT_TYPES and str(p.get("content_type_id")) != "15"]
    conditions = (session.view or {}).get("conditions") or []
    before = {it["candidate_id"] for it in plan["days"][day]["items"]}
    _apply_pins(plan["days"], {day: cid})
    _gather_around_festivals(plan["days"], {day: cid}, cand_map, sights, cid_of, conditions,
                             keep_cids={cid_of(e["place"]) for e in session.user_places})
    _sync_festivals(session, plan, cand_map)
    body = _replan_user_places(session)  # 숙소 주변 모으기·내가 고른 장소를 다시 반영하고 시간표를 새로 그린다
    dropped = len(before - {it["candidate_id"] for it in plan["days"][day]["items"]} - {cid})
    how = (f"축제장에서 먼 장소 {dropped}곳은 가까운 곳으로 바꿔서 그날 시간표를 다시 맞췄어요." if dropped
           else "그날 시간표를 다시 맞췄어요 (나머지 장소는 축제장에서 가까워 그대로 뒀어요).")
    reply = f"🎉 **{pick['title']}** 을(를) {day + 1}일차({_md(dates[day].replace('-', ''))})에 추가했어요. {how}\n\n{body}{_fest_time_prompt(session)}"
    session.history.append({"role": "assistant", "content": reply})
    return _pack(session, "planned", reply)


def _period(p: dict) -> str:
    a, b = _md(p.get("event_start")), _md(p.get("event_end") or p.get("event_start"))
    return a if a == b else f"{a} ~ {b}"


def _md(d: str) -> str:
    return f"{d[4:6]}/{d[6:8]}" if len(d or "") >= 8 else ""


def _fest_time_prompt(session: ChatSession) -> str:
    """시간을 모르는 축제를 사용자가 찾아서 알려주도록 안내한다 (축제마다 한 번만)."""
    todo = [(k, v) for k, v in session.fest_pins.items() if k not in session.fest_times and not v["asked"]]
    if not todo:
        return ""
    lines = ["", "---", "⏰ **축제 시간은 저희가 알 수 없어요.** 사용자님이 공식 홈페이지나 포스터에서 시간을 찾아서 알려주셔야 "
             "그 시간에 맞춰 나머지 일정을 정확하게 조율해 드릴 수 있어요. 지금은 시간이 정해지지 않아서 임의의 시간대에 넣어 둔 상태예요."]
    for k, v in todo:
        period = f" ({_md(v['start'])}~{_md(v['end'])} 개최)" if v["start"] else ""
        lines.append(f"- {v['day'] + 1}일차 **{v['title']}**{period} → 예: \"{_fest_core(v['title']) or v['title']} 저녁 7시부터 9시\"")
        v["asked"] = True
    return "\n".join(lines)


def _rerender(session: ChatSession) -> str:
    """AI를 부르지 않고, 지금 일정에 사용자가 알려준 축제 시간만 반영해서 다시 그린다."""
    view, s = session.view or {}, session.slots
    conditions = view.get("conditions") or []
    days_view = hydrate_plan(session.plan, session.last_cand_map, conditions, session.restaurants, _fixed_map(session), _lodging_for(session), _stay_times_eff(session))
    session.view = {**view, "plan": days_view}
    return render_markdown("", days_view, conditions, "", [], place_label=s["area"] or s["region"])


def _user_place_ack(session: ChatSession) -> str:
    """방금 메시지에서 읽은 숙소·장소를 사용자에게 되짚어 준다 (잘못 읽었으면 바로잡을 수 있게)."""
    ack, session.pending_ack = session.pending_ack, None
    stay_new, session.pending_stay = session.pending_stay, None
    if not ack and not stay_new:
        return ""
    ack = ack or {}
    lines = ["📌 **이렇게 이해했어요**"]
    if ack.get("lodging"):
        lo = ack["lodging"]
        warn = " ⚠️ 말씀하신 이름과 완전히 같지는 않아요. 맞는 곳인지 확인해 주세요." if lo.get("approx") else ""
        lines.append(f"- 🏨 숙소: **{lo['title']}** ({lo['addr']}) — 매일 여기서 출발해서 여기로 돌아오는 동선으로 짤게요{warn}")
    if stay_new:
        parts = []
        if "in" in stay_new:
            parts.append(f"체크인 {hhmm(stay_new['in'])}")
        if "out" in stay_new:
            parts.append(f"체크아웃 {hhmm(stay_new['out'])}")
        if "in" in stay_new and "out" in stay_new:
            how = "첫날은 그 시간에 맞춰 숙소에 들러 체크인하고, 마지막 날은 체크아웃 시간 전에 나올게요"
        elif "in" in stay_new:
            how = "첫날은 그 시간에 맞춰 숙소에 들러 체크인할게요"
        else:
            how = "마지막 날은 체크아웃 시간 전에 나올게요"
        lines.append(f"- 🕒 {' · '.join(parts)} — {how}")
    for e in ack.get("added", []):
        p, tm = e["place"], e.get("time")
        when = f"{e['assigned_day'] + 1}일차 " if e.get("assigned_day") is not None else ""
        if tm:
            end = tm[1] if tm[1] else tm[0] + stay_minutes(p)
            when += f"{hhmm(tm[0])} ~ {hhmm(end)} 고정"
        else:
            when += "시간은 정하지 않고 근처 일정과 함께"
        warn = " ⚠️ 말씀하신 이름과 완전히 같지는 않아요. 맞는 곳인지 확인해 주세요." if p.get("approx") else ""
        lines.append(f"- 📍 **{p['title']}** ({p['addr']}) — {when}{warn}")
    for p in ack.get("removed", []):
        lines.append(f"- 🗑 **{p['title']}** 은(는) 일정에서 뺐어요")
    for name in ack.get("unresolved_stay", []):  # 일정이 이미 있을 때: 숙소는 아직 반영하지 못했다
        lines.append(f"- ❓ 숙소 '{name}' 위치를 찾지 못해서 아직 반영하지 못했어요. 정확한 이름이나 주소를 다시 알려주세요.")
    for name in ack.get("unresolved", []):
        lines.append(f"- ❓ '{name}' 위치를 찾지 못했어요. 지역을 붙여 정확한 이름으로 다시 알려주세요 (예: \"성남 단풍 카페\")")
    if len(lines) == 1:
        return ""
    added = [e["place"]["title"] for e in ack.get("added", []) if isinstance(e, dict) and e.get("place")]
    tail = "다르게 읽은 부분이 있으면 다시 말씀해 주세요."
    if added:  # 사용자가 실제로 말한 장소 이름으로만 예시를 든다
        tail += f" 다른 날로 옮기려면 \"{added[0]} 2일차로 옮겨줘\"처럼 말씀하시면 돼요."
    lines.append(tail)
    return "\n".join(lines) + "\n\n"


def _region_matcher(slots: dict):
    """여행 시도 안의 주소인지 (시도 이름과 별칭으로 확인). 시도를 아직 모르면 거르지 않는다."""
    region = slots.get("region")
    if not region or region not in SIDO:
        return None
    names = [region, *SIDO[region]["aliases"]]
    return lambda addr: any(n in (addr or "") for n in names)


DEFAULT_CHECK_IN, DEFAULT_CHECK_OUT = 15 * 60, 11 * 60  # 숙소를 알려주면 첫날 15시 체크인, 마지막 날 11시 체크아웃으로 고정


def _stay_times_eff(session: ChatSession) -> dict:
    """체크인·체크아웃 시각 (사용자가 따로 말하지 않았으면 기본값)."""
    return {"in": DEFAULT_CHECK_IN, "out": DEFAULT_CHECK_OUT, **session.stay_times}


def _stay_notice(session: ChatSession) -> str:
    """숙소를 알려줬을 때 체크인·체크아웃 시각과, 바꾸는 방법을 한 번 알려준다 (당일치기는 안내하지 않는다)."""
    s = session.slots
    if session.asked_stay_times or _lodging_for(session) is None:
        return ""
    if s.get("start_date") and s.get("start_date") == s.get("end_date"):
        return ""
    session.asked_stay_times = True
    t = _stay_times_eff(session)
    return (f"🏨 숙소 체크인은 첫날 {hhmm(t['in'])}, 체크아웃은 마지막 날 {hhmm(t['out'])}으로 맞춰 뒀어요. "
            "바꾸고 싶으면 일정을 '내 여행'에 저장한 뒤 **여행 일정 상세 페이지**에서 직접 고쳐 주세요.")


def _lodging_hold_reply(session: ChatSession) -> str:
    """숙소 기준으로 짜 달라고 했는데 숙소를 못 찾았을 때: 마음대로 다른 일정을 만들지 않고 숙소를 다시 묻는다."""
    return (f"🏨 말씀하신 숙소 **'{session.lodging_hold}'** 의 위치를 찾지 못했어요.\n\n"
            "숙소를 기준으로 동선을 짜 드리려고 했기 때문에, 숙소 위치 없이 일정을 먼저 만들지는 않고 기다릴게요.\n"
            "- 정확한 숙소 이름이나 도로명 주소를 다시 알려주세요 (예: \"신라모노그램 강릉\" 또는 \"강원 강릉시 해안로 210\")\n"
            "- 숙소 없이 일정만 먼저 보고 싶으시면 \"숙소 없이 진행\"이라고 말씀해 주세요")


def _same_name(a: str, b: str) -> bool:
    x, y = re.sub(r"[\W_]+", "", a), re.sub(r"[\W_]+", "", b)
    return bool(x and y) and (x in y or y in x)


def _try_user_places(session: ChatSession, text: str) -> dict | None:
    """
    "숙소는 OO호텔, 2일차 12시에 OO카페 들를게" 같은 말에서 숙소·꼭 들를 장소(와 시간)를 읽어 세션에 기록한다.
    일정이 이미 있고 장소 말만 있으면 AI 없이 바로 반영해 답한다. 그 밖에는 None을 돌려주고 보통 흐름이 이어진다
    (이때 읽은 내용은 session.pending_ack 에 남아 답변 앞에 붙고, 일정을 만들 때 반영된다).
    """
    known = lambda seg: any(_names_festival(seg, v["title"]) for v in session.fest_pins.values())  # 축제 시간 말은 축제 쪽이 맡는다
    parsed = parse_directives(text, known)
    if session.lodging_hold:  # 숙소를 못 찾아 되물은 상태
        if NO_LODGING_RE.search(text):
            session.lodging_hold, session.rest_text = "", ""  # "숙소 없이 진행" → 숙소 없이 일정을 만든다 (이 말 자체는 취향이 아니다)
            return None
        if not any(i["kind"] == "stay" for i in parsed["items"]):
            reply_item = lodging_item_from_reply(text)  # "신라모노그램 강릉 경포"처럼 이름만 답해도 숙소로 읽는다
            if reply_item is not None:
                parsed["items"].insert(0, reply_item)
                parsed["rest"], parsed["only"] = "", True  # 이름만 답한 말은 통째로 숙소 이름 (취향으로 저장되지 않는다)
    if not parsed["items"]:
        return None
    s = session.slots
    hint = s["area"] or s["region"] or ""
    pool = list((session.raw or {}).get("places", [])) + list(session.last_cand_map.values())
    ack: dict = {"lodging": None, "added": [], "removed": [], "unresolved": [], "unresolved_stay": []}
    warns: list[str] = []
    changed = False
    for it in parsed["items"]:
        if it["kind"] == "drop":
            for e in [e for e in session.user_places if _same_name(it["name"], e["place"]["title"])]:
                session.user_places.remove(e)
                ack["removed"].append(e["place"])
                cid = session.id_map.get(key_of(e["place"]))
                for d in (session.plan or {}).get("days", []):
                    d["items"] = [x for x in d["items"] if x["candidate_id"] != cid]
                changed = True
            if session.lodging and _same_name(it["name"], session.lodging["title"]):
                ack["removed"].append(session.lodging)
                session.lodging, changed = None, True
            continue
        if it["kind"] == "move":  # 이미 말한 장소의 날짜만 바꾼다 (새 장소를 찾지는 않는다)
            for e in session.user_places:
                if _same_name(it["name"], e["place"]["title"]):
                    e["day_ref"], changed = it["day"], True
                    ack["added"].append(e)
            continue
        place, warn = find_place(it, hint, pool, search_local, _region_matcher(s))
        if warn:
            warns.append(warn)
        if place is None:
            if it["kind"] == "stay":
                shown = it.get("display") or it["name"]
                if session.plan:
                    ack["unresolved_stay"].append(shown)
                else:
                    session.lodging_hold = shown  # 숙소 기준으로 짜 달라는 요청이니, 못 찾았으면 일정을 만들지 않고 되묻는다
            elif it["strong"]:
                ack["unresolved"].append(it["name"])
            continue
        changed = True
        if it["kind"] == "stay":
            session.lodging, ack["lodging"], session.lodging_hold = place, place, ""
            continue
        entry = {"place": place, "day_ref": it["day"], "time": it["time"], "ctx": (s["region"], s["area"]) if s["region"] else None,
                 "assigned_day": None}
        old = next((e for e in session.user_places if key_of(e["place"]) == key_of(place)), None)
        if old is not None:  # 같은 장소를 다시 말하면 시간·날짜만 새로 고친다 ("OO카페 4시로 바꿔줘")
            entry["day_ref"] = it["day"] if it["day"] is not None else old.get("day_ref")
            entry["time"] = it["time"] if it["time"] is not None else old.get("time")
            session.user_places[session.user_places.index(old)] = entry
        else:
            session.user_places.append(entry)
        ack["added"].append(entry)
    if not (changed or ack["unresolved"] or ack["unresolved_stay"] or session.lodging_hold):
        return None  # 장소 말이 아니었다 (일상 표현이 우연히 걸린 경우)
    session.pending_ack = ack
    session.rest_text = parsed["rest"]  # 숙소·장소 문장은 지역·날짜·취향 읽기에 넘기지 않는다
    if not (parsed["only"] and session.plan and session.view):
        return None
    reply = _replan_user_places(session)
    prefix = _user_place_ack(session)
    if warns:
        session.view = {**(session.view or {}), "caveats": [*(session.view or {}).get("caveats", []), *warns]}
    ask = _stay_notice(session)
    reply = prefix + reply + (f"\n\n---\n{ask}" if ask else "")
    session.history.append({"role": "assistant", "content": reply})
    return _pack(session, "planned", reply)


def _replan_user_places(session: ChatSession) -> str:
    """AI 없이, 지금 일정에 사용자 장소·숙소를 반영해 다시 그린다."""
    view = session.view or {}
    conditions = view.get("conditions") or []
    sights = [p for p in (session.raw or {}).get("places", []) if p["content_type_id"] in SIGHT_TYPES]
    _apply_user_places(session, session.plan["days"], session.last_cand_map, lambda p: _cid(session, p), conditions, sights,
                       {i for i, d in enumerate(session.plan["days"])
                        if any(str((session.last_cand_map.get(it["candidate_id"]) or {}).get("content_type_id")) == "15" for it in d["items"])})
    return _rerender(session)


def _try_festival_time(session: ChatSession, text: str) -> dict | None:
    """일정에 축제가 있을 때 "불꽃축제 저녁 7시부터 9시" 같은 말이면, 그 시간에 맞춰 일정을 다시 조율한다. 해당 없으면 None."""
    if not (session.plan and session.fest_pins and session.view):
        return None
    tr = parse_time_range(text)
    if tr is None:
        return None
    pins = session.fest_pins
    named = [k for k, v in pins.items() if _names_festival(text, v["title"])]
    if not (named or FEST_RE.search(text)):
        # 축제 말이 없어도 안내 직후의 짧은 답("저녁 7시부터 9시")은 받아준다. 다른 수정 요청은 건드리지 않는다
        if not session.awaiting_fest_time or len(text) > 30 or MODIFY_RE.search(text):
            return None
    target = None
    if len(pins) == 1:
        target = next(iter(pins))
    elif len(named) == 1:
        target = named[0]
    else:
        days = _target_days(text, len(session.plan["days"]))
        on_day = [k for k, v in pins.items() if v["day"] in days]
        pending = [k for k in pins if k not in session.fest_times]
        target = on_day[0] if len(on_day) == 1 else (pending[0] if len(pending) == 1 else None)
    if target is None:
        names = "\n".join(f"- {v['day'] + 1}일차 {v['title']}" for v in pins.values())
        reply = f"어느 축제의 시간인지 알려주세요.\n{names}\n(예: \"1일차 축제 저녁 7시부터 9시\")"
        session.history.append({"role": "assistant", "content": reply})
        return _pack(session, "planned", reply)
    v = pins[target]
    place = next((p for p in session.last_cand_map.values() if (p.get("content_id") or p.get("title")) == target), {})
    start, end = tr
    end_shown = end if end else start + stay_minutes(place or {"content_type_id": "15"})
    session.fest_times[target] = (start, end)
    session.awaiting_fest_time = any(k not in session.fest_times for k in pins)
    reply = (f"⏰ **{v['title']}** 시간을 **{hhmm(start)} ~ {hhmm(end_shown)}** 에 맞춰, 그 시간은 그대로 두고 "
             f"{v['day'] + 1}일차의 나머지 일정을 다시 조율했어요. 시간이 다르면 다시 알려주세요.\n\n") + _rerender(session)
    session.history.append({"role": "assistant", "content": reply})
    return _pack(session, "planned", reply)


def _make_plan(session: ChatSession, text: str, today: date, ranker, refine: bool, warnings: list[str]) -> str:
    t_start = time.perf_counter()
    s = session.slots
    sido, area = s["region"], s["area"]
    start, end = parse_iso(s["start_date"]), parse_iso(s["end_date"])
    include_food = True  # 식사 장소를 실제 음식점으로 채우기 위해 항상 수집
    if wants_food(text) and not wants_food(s["preferences"]):
        s["preferences"] = _merge_text(s["preferences"], "맛집")  # 식당 순위에 반영

    # 1) 데이터 수집 (같은 여행 조건이면 재사용)
    key = (sido, area, s["start_date"], s["end_date"], include_food)
    stale = (session.raw is None or session.raw_key != key
             or time.time() - session.raw["fetched_at"] > CONTEXT_TTL_SEC)
    if stale:
        if session.raw_key is None or session.raw_key[:4] != key[:4]:
            session.id_map, session.plan, session.last_cand_map, refine = {}, None, {}, False
            session.fest_pins, session.fest_times, session.awaiting_fest_time = {}, {}, False
        check_cancelled()
        set_progress(f"{area or sido}의 날씨·미세먼지·관광지·소식을 모으고 있어요")
        session.raw = gather_raw(sido, area, start, end, include_food, today)
        session.raw_key = key
    raw = session.raw
    t_gathered = time.perf_counter()

    # 2) 일자별 컨디션 (날씨·미세먼지)
    dates = [(start + timedelta(days=i)).isoformat() for i in range((end - start).days + 1)]
    conditions = build_day_conditions(start, end, raw["weather"], raw["air"]["by_date"])
    bad_days = sum(1 for c in conditions if c["outdoor_ok"] is False)

    # 축제·행사는 사용자가 축제를 말했을 때만 일정에 넣는다 (말하지 않았는데 일정에 끼어들고 시간을 되묻지 않게)
    pins = _festival_pins(session, text, raw, dates)  # 꼭 넣을 축제 {일차: 축제}
    want_reco, hint_day = session.want_fest_reco, session.fest_hint_day  # 축제 추천을 부탁했으면 일정에는 넣지 않고 후보만 보여준다
    session.want_fest_reco = False  # fest_hint_day 는 남겨 둔다 (추천받은 축제를 추가할 때 어느 날에 넣을지 쓴다)
    wants_fest = bool(pins) or (bool(FEST_RE.search(f"{s['preferences']} {text}")) and not want_reco)
    sight_types = SIGHT_TYPES if wants_fest else SIGHT_TYPES - {"15"}
    sights = [p for p in raw["places"] if p["content_type_id"] in sight_types]
    if area and sights and len(sights) < len(dates) * 4 + 4 and not raw.get("expanded"):
        # 작은 시·군은 긴 일정(최대 30일)을 채울 장소가 모자라다 → 같은 시도의 가까운 장소를 거리순으로 보충
        _expand_nearby(raw, sido, area, start, end)
        sights = [p for p in raw["places"] if p["content_type_id"] in sight_types]
    eateries = [p for p in raw["places"] if p["content_type_id"] == "39"]

    if not sights:
        # 후보가 하나도 없으면 빈 일정을 만들지 않는다. 다음 요청에서 다시 수집하도록 캐시도 비운다.
        session.raw = session.raw_key = None
        session.view = {"plan": None, "conditions": conditions, "risks": [], "used_sources": [],
                        "caveats": _caveats(raw, conditions, warnings, start, end, today)}
        return f"지금은 {area or sido} 일정에 넣을 장소를 찾지 못했어요. 잠시 뒤에 다시 말씀해 주시거나 다른 지역으로 알려주세요."

    # 3) 후보 선별: 취향과 유사한 순 + 궂은 날을 위한 실내 후보 보장
    #    여행 기간 전체에 쓸 후보(하루 4곳 + 여유)를 한 번에 고른다. AI에는 아래 4)에서 며칠 치씩 나눠 보낸다.
    # 이번에 취향을 말하지 않았으면 지난 여행에서 자주 담은 종류를 반영한다 (말한 취향이 항상 우선)
    profile = _profile_of(session)
    taste = [] if (s["preferences"] or refine) else taste_words(profile)
    query = " ".join(x for x in [sido, area, s["party"], s["preferences"] or " ".join(taste), text if refine else ""] if x)
    set_progress("취향에 맞는 장소를 고르고 있어요")
    # 그 지역 장소는 취향 유사도 순, 보충한 주변 장소는 그 뒤에 가까운 순
    ranked = rank_places([p for p in sights if not p.get("nearby")], sido, query, ranker) + [p for p in sights if p.get("nearby")]
    ranked = push_visited_back(ranked, profile)  # 저장했던 장소보다 새로운 곳을 먼저
    restaurants = (rank_places([p for p in eateries if not p.get("nearby")], sido, query, ranker)
                   + [p for p in eateries if p.get("nearby")])[:max(30, len(dates) * 3)]  # 식사 장소 후보
    wants_activity = bool(ACTIVITY_RE.search(f"{s['preferences']} {text}"))
    caps = {} if wants_activity else {"28": 3}  # 액티비티를 원한다고 하지 않았으면 레포츠가 후보를 독차지하지 않게
    pool = select_candidates(ranked, max(6, len(dates) * 5 + 4), min(2 * bad_days + 1, 8 + bad_days) if bad_days else 0, caps)
    if refine and session.last_cand_map:  # 수정 요청일 때 기존 일정의 장소는 계속 후보에 포함
        keys = {(p["content_id"] or p["title"]) for p in pool}
        pool += [p for p in session.last_cand_map.values() if (p["content_id"] or p["title"]) not in keys]
    keys = {(p["content_id"] or p["title"]) for p in pool}
    pool += [p for p in pins.values() if (p["content_id"] or p["title"]) not in keys]
    warnings += enrich(pool)

    def cid_of(p):
        k = p["content_id"] or p["title"]
        if k not in session.id_map:
            session.id_map[k] = f"C{len(session.id_map) + 1}"
        return session.id_map[k]

    cand_map = {cid_of(p): p for p in pool}  # 순위순
    pin_cids = {i: cid_of(p) for i, p in pins.items()}
    news_by_id = {n["id"]: n for n in raw["news"]}
    news_lines = [f"{n['id']} | [{n['category']}] {n['pub_date']} | {n['title']} | {n['description'][:100]}" for n in raw["news"][:CHAT_MAX_NEWS]]

    # 4) LLM 일정 생성/수정 (긴 일정은 CHAT_PLAN_CHUNK_DAYS일씩 나눠서)
    mode = "수정" if refine and session.plan else "새 일정"
    groups = _day_groups(len(dates), text, mode)
    current_text = _plan_text(session.plan, session.last_cand_map, dates) if mode == "수정" else ""
    old_days = [{"theme": d["theme"], "items": list(d["items"])} for d in session.plan["days"]] if mode == "수정" else None
    t_ranked = time.perf_counter()
    grounding: dict = {"proposed": 0, "dropped": 0}
    merged = old_days or [{"theme": "", "items": []} for _ in dates]
    message, follow, llm_stats = "", "", {}
    ok_groups, question_reply = 0, None
    failed_days: set[int] = set()
    any_llm_error = False
    used: set[str] = set()  # 앞 묶음에서 쓴 장소 (새 일정에서 다음 묶음 후보로 다시 보내지 않음)
    for gi, idxs in enumerate(groups):
        set_progress("AI가 일정을 짜고 있어요" + (f" ({gi + 1}/{len(groups)})" if len(groups) > 1 else ""))
        sub_dates = [dates[i] for i in idxs]
        sub_map = _group_candidates(idxs, mode, old_days, cand_map, used, conditions)
        sub_map.update({pin_cids[i]: cand_map[pin_cids[i]] for i in idxs if i in pin_cids})
        note = "" if len(groups) == 1 else f"\n(전체 {len(dates)}일 일정을 나눠서 짜는 중: 이번에는 {', '.join(f'{i + 1}일차' for i in idxs)})"
        user_msg = build_plan_user_message(
            mode=mode, region_label=_label(s), start=sub_dates[0], end=sub_dates[-1], n_days=len(sub_dates),
            party=s["party"], preferences=s["preferences"], avoid=s["avoid"],
            condition_lines=[prompt_line(conditions[i]) for i in idxs],
            candidate_lines=[_cand_line(cid, p, news_by_id) for cid, p in sub_map.items()],
            news_lines=news_lines, current_plan_text=current_text, user_request=text + note,
            target_dates=sub_dates if len(groups) > 1 or len(idxs) < len(dates) else None,
            must_include=[f"{pin_cids[i]} → {dates[i]}" for i in idxs if i in pin_cids],
        )
        parsed, raw_txt, llm_error = None, "", False
        try:
            parsed, raw_txt = _llm_json(
                [{"role": "system", "content": PLAN_SYSTEM_PROMPT}, *_history_for_llm(session), {"role": "user", "content": user_msg}],
                temperature=0.4,
            )
        except Exception as e:
            llm_error = any_llm_error = True
            warnings.append(f"AI 연결 문제로 일정 생성/수정을 하지 못했어요 ({type(e).__name__}: {str(e)[:500]})")
        llm_stats = dict(LAST_STATS)
        g: dict = {}
        sub_plan, w = normalize_plan(parsed, sub_map, sub_dates, g)
        grounding["proposed"] += g.get("proposed", 0)
        grounding["dropped"] += g.get("dropped", 0)
        warnings += w
        if not llm_error and sub_plan is None:
            # 오류 없이 응답했는데 못 쓰는 경우: 무슨 응답이었는지 보여준다 (원인 파악용)
            if not raw_txt.strip():
                warnings.append("AI가 빈 응답을 돌려줬어요. 모델이 '생각'만 하고 답을 못 냈을 수 있어요 (.env에 OLLAMA_THINK=false 를 넣어보세요).")
            elif parsed is None:
                warnings.append(f"AI 응답을 JSON으로 읽지 못했어요 (응답 앞부분: {raw_txt[:100]!r})")
            else:
                warnings.append("AI 응답에 쓸 수 있는 일정이 없었어요 (장소 id를 맞추지 못했을 수 있어요).")
        if sub_plan is not None and sub_plan["days"] is None:
            if mode == "수정" and gi == 0:
                question_reply = sub_plan  # 일정 변경이 아닌 질문·인사: 나머지 묶음은 부르지 않는다
                break
            sub_plan = None  # 새 일정인데 days가 없으면 그 묶음은 실패로 간주
        if sub_plan is None:
            failed_days.update(idxs)
            if llm_error:  # AI에 연결이 안 되면 나머지 묶음도 실패하므로 기다리지 않고 규칙으로 채운다
                failed_days.update(i for later in groups[gi + 1:] for i in later)
                break
            continue
        ok_groups += 1
        message, follow = message or sub_plan["message"], sub_plan["follow_up"] or follow
        for i, day in zip(idxs, sub_plan["days"]):
            merged[i] = day
            used.update(it["candidate_id"] for it in day["items"] if it["candidate_id"])
    t_llm_done = time.perf_counter()

    plan, plan_source = None, "llm"
    if question_reply is not None:
        plan = question_reply
    elif ok_groups:
        plan = {"message": message, "days": merged, "follow_up": follow}
        if mode == "새 일정" or failed_days:
            # AI가 비우거나 적게 넣은 날(또는 실패한 묶음의 날)을 남은 후보로 채운다. 수정에서는 사용자가 줄인 날을 건드리지 않음
            added = fill_thin_days(merged, dates, conditions, _fill_order(cand_map, s, text), cand_map,
                                   only=None if mode == "새 일정" else failed_days)
            if added:
                warnings.append(f"AI가 채우지 못한 자리 {added}곳을 가까운 후보로 채웠어요.")

    if plan is None and mode == "수정" and pins:
        # AI 없이도 축제 기준 수정은 할 수 있다: 기존 일정에 축제를 그 날짜로 넣는다 (아래 _apply_pins)
        plan = {"message": "", "days": [{"theme": d["theme"], "items": list(d["items"])} for d in old_days], "follow_up": ""}
        plan_source = "fallback"
    if plan is None and mode == "수정":
        # 수정 실패: 기존 일정은 그대로 두고 알려준다
        if not any_llm_error:
            warnings.append("AI 응답을 이해하지 못해 일정을 바꾸지 못했어요.")
        session.view = {**(session.view or {}), "caveats": _caveats(raw, conditions, warnings, start, end, today)}
        return "죄송해요, 지금은 요청하신 수정을 반영하지 못했어요. 잠시 후 다시 말씀해 주시거나 표현을 바꿔서 알려주세요."
    if plan is None:
        plan = fallback_plan(dates, conditions, _fill_order(cand_map, s, text), cand_map)
        plan_source = "fallback"
        warnings.append("AI 일정 대신 규칙 기반 기본 일정을 보여드려요.")

    if plan["days"] is None:  # 질문·감사 등: 일정은 그대로, 답만 한다
        reply = plan["message"]
        session.view = {**(session.view or {}), "caveats": _caveats(raw, conditions, warnings, start, end, today)}
        return reply

    if pin_cids:
        _apply_pins(plan["days"], pin_cids)
        fill_thin_days(plan["days"], dates, conditions, _fill_order(cand_map, s, text), cand_map)
        _gather_around_festivals(plan["days"], pin_cids, cand_map, sights, cid_of, conditions)  # 나머지는 축제장 주변으로
    frozen = {cid for cid, p in cand_map.items() if p.get("content_type_id") == "15"}  # 축제는 날짜가 정해져 있다
    # 영업시간·휴무일: 일정에 넣은 장소부터, 남는 한도로 바꿔 넣을 후보까지 조회 (7일 저장)
    closure_notes = []
    if INTRO_PLAN_LIMIT > 0:
        set_progress("영업시간·휴무일을 확인하고 있어요")
        in_plan = list(dict.fromkeys(it["candidate_id"] for d in plan["days"] for it in d["items"] if it.get("candidate_id") in cand_map))
        todo = [cand_map[c] for c in in_plan] + [p for c, p in cand_map.items() if c not in set(in_plan)]
        todo = [p for p in todo if "intro" not in p and p.get("content_type_id") in ("12", "14", "28", "38", "39")]
        if todo:
            warnings += enrich_intro(todo, INTRO_PLAN_LIMIT)
        closure_notes = fix_closures(plan["days"], cand_map, conditions, frozen | set(pin_cids.values()))
    if mode == "새 일정":  # 날짜 사이 장소 맞바꾸기로 하루 장소를 가까이 모은다 (수정 요청은 사용자가 고친 걸 흔들지 않게 제외)
        frozen |= {it["candidate_id"] for i in pin_cids for it in plan["days"][i]["items"]}  # 축제장 주변으로 모은 날
        rebalance_days(plan["days"], cand_map, conditions, frozen)
    _apply_user_places(session, plan["days"], cand_map, cid_of, conditions, sights, set(pin_cids))  # 사용자가 말한 장소·시간 반영

    # 5) 구조화 + 렌더링
    set_progress("일정을 정리하고 있어요")
    session.plan, session.last_cand_map = plan, {cid: p for cid, p in cand_map.items()}
    session.restaurants = restaurants
    _sync_festivals(session, plan, cand_map)
    days_view = hydrate_plan(plan, cand_map, conditions, restaurants, _fixed_map(session), _lodging_for(session), _stay_times_eff(session))
    # 일정을 물었으니 일정만 답한다 (뉴스·마무리 질문 같은 묻지 않은 내용은 붙이지 않음. 뉴스는 risks 필드에만 남김)
    reply = render_markdown(plan["message"], days_view, conditions, "", [], place_label=area or sido)
    if pins:
        festivals = ", ".join(f"{i + 1}일차 {p['title']}" for i, p in sorted(pins.items()))
        reply = f"🎉 축제 기간에 맞춰 넣고, 그날의 나머지 장소는 축제장 주변에서 골랐어요: {festivals}\n\n{reply}"
    if taste:
        reply = f"💡 지난 여행에서 자주 담으신 {'·'.join(taste)} 취향을 반영했어요. 원하는 취향을 말씀하시면 바꿔 드릴게요.\n\n" + reply
    if closure_notes:
        reply = "🕒 휴무일을 확인해서 고쳤어요: " + " / ".join(closure_notes) + "\n\n" + reply
    reply += _fest_time_prompt(session)
    ask = _stay_notice(session)  # 숙소가 있으면 체크인·체크아웃 시각과 고치는 방법을 일정 아래에 한 번 알려준다
    if ask:
        reply += f"\n\n---\n{ask}"
    if want_reco:
        offer, offer_warns = _festival_offer(session, ranker, dates, hint_day, sido, area, query, start, end)
        warnings += offer_warns
        reply += f"\n\n---\n{offer}"

    sources = ["tourism"]
    if raw["news"]:
        sources.append("naver_news")
    if raw["weather"]:
        sources.append("weather")
    if raw["air"]["by_date"]:
        sources.append("air_quality")
    timings = {"collect_sec": round(t_gathered - t_start, 1), "rank_sec": round(t_ranked - t_gathered, 1),
               "llm_sec": round(t_llm_done - t_ranked, 1), "tasks": raw.get("timings", {})}
    session.view = {
        "timings": timings,
        # 일정 품질 지표 (개발자 모드·evaluate.py). 이 일정을 만든 응답에만 한 번 싣는다 (_pack 에서 꺼냄)
        "evaluation": evaluate_plan(days_view, grounding, plan_source, timings),
        "llm_stats": llm_stats,
        "plan": days_view, "conditions": conditions, "used_sources": sources,
        "risks": [{"category": n["category"], "title": n["title"], "link": n["link"], "pub_date": n["pub_date"]} for n in raw["news"]],
        "caveats": _caveats(raw, conditions, warnings, start, end, today),
    }
    return reply


# 일차를 가리키는 말: "3일차", "셋째 날", "2번째 날", "첫날", "마지막 날"
_ORDINAL = {"첫": 1, "둘": 2, "셋": 3, "넷": 4, "다섯": 5, "여섯": 6, "일곱": 7, "여덟": 8, "아홉": 9, "열": 10}
_DAY_REF_RE = re.compile(r"(\d{1,2})\s*일\s*차|(\d{1,2})\s*번?\s*째\s*날|(첫|둘|셋|넷|다섯|여섯|일곱|여덟|아홉|열)\s*(?:째)?\s*날|(마지막|끝)\s*날")


def _target_days(text: str, n: int) -> list[int]:
    """수정 요청에서 말한 일차(0부터). 없으면 빈 리스트."""
    out = set()
    text = re.sub(r"첫\s*번\s*째", "1번째", re.sub(r"두\s*번\s*째", "2번째", re.sub(r"세\s*번\s*째", "3번째", re.sub(r"네\s*번\s*째", "4번째", text or ""))))
    for m in _DAY_REF_RE.finditer(text):
        k = int(m.group(1) or m.group(2)) if (m.group(1) or m.group(2)) else (_ORDINAL[m.group(3)] if m.group(3) else n)
        if 1 <= k <= n:
            out.add(k - 1)
    return sorted(out)


def _day_groups(n: int, text: str, mode: str) -> list[list[int]]:
    """
    AI를 몇 번에 나눠 부를지: 일차 순번 묶음의 리스트.
    - CHAT_PLAN_CHUNK_DAYS일 이하는 한 번에 (지금까지와 같음)
    - 긴 일정은 CHAT_PLAN_CHUNK_DAYS일씩. 수정 요청에서 특정 일차를 말했으면 그 날만 다시 짠다.
    """
    if n <= CHAT_PLAN_CHUNK_DAYS:
        return [list(range(n))]
    if mode == "수정":
        target = _target_days(text, n)
        if target:
            return [target[i:i + CHAT_PLAN_CHUNK_DAYS] for i in range(0, len(target), CHAT_PLAN_CHUNK_DAYS)]
    return [list(range(i, min(i + CHAT_PLAN_CHUNK_DAYS, n))) for i in range(0, n, CHAT_PLAN_CHUNK_DAYS)]


def _group_candidates(idxs: list[int], mode: str, old_days: list[dict] | None, cand_map: dict, used: set[str],
                      conditions: list[dict]) -> dict:
    """
    한 묶음(며칠)에 보낼 후보. 앞 묶음에서 쓴 장소와 다른 날 일정에 있는 장소는 빼고 순위순으로 고른다.
    수정 요청이면 그 날들에 원래 있던 장소를 먼저 넣는다. 묶음 일수×5+2곳은 항상 보낸다 (하루 3~5곳).
    """
    k = max(CHAT_MAX_CANDIDATES, len(idxs) * 5 + 2)
    bad = sum(1 for i in idxs if conditions[i]["outdoor_ok"] is False)
    own: list[str] = []
    taken = set(used)
    if old_days:
        for i, day in enumerate(old_days):
            for it in day["items"]:
                if it["candidate_id"] not in cand_map:
                    continue
                if i in idxs:
                    own.append(it["candidate_id"])
                else:
                    taken.add(it["candidate_id"])
    rest = [cid for cid in cand_map if cid not in taken and cid not in own]
    picked = select_candidates([cand_map[cid] for cid in rest], max(k - len(own), len(idxs) * 3),
                               min(2 * bad + 1, 8) if bad else 0)
    ids = {id(p) for p in picked}
    return {**{cid: cand_map[cid] for cid in own}, **{cid: p for cid, p in cand_map.items() if id(p) in ids and cid not in own}}


def _fill_order(cand_map: dict, s: dict, text: str) -> list[str]:
    """규칙으로 채울 때의 후보 순서: 순위순, 액티비티를 원한다고 하지 않았으면 레포츠(28)는 뒤로."""
    order = list(cand_map)  # cand_map은 순위순
    if not ACTIVITY_RE.search(f"{s['preferences']} {text}"):
        order.sort(key=lambda cid: str(cand_map[cid].get("content_type_id")) == "28")
    return order


def detect_intent(text: str, session: "ChatSession") -> str:
    """
    'about'(내부 정보 문의) | 'news'(지역 소식) | 'place_info'(특정 장소 정보) | 'plan'(일정)
    | 'recommend'(여행지) | 'food'(맛집·카페) | 'stay'(숙박) | 'festival'(축제·행사) | 'course'(추천 여행코스 목록).
    - 일정 관련 단어가 있거나 일정 수정 요청이면 plan
    - 동행·취향을 묻는 중이거나 일정이 이미 있을 때는 '알려줘/추천해줘' 같은 요청 표현이 있어야 단발 요청으로 본다
      (예: "맛집 위주로 가고 싶어요"는 취향 답변이지 맛집 목록 요청이 아님)
    """
    s = session.slots
    in_plan = session.plan is not None
    mid = bool(s["region"] and s["start_date"] and s["end_date"]) and not in_plan
    if ABOUT_RE.search(text):
        return "about"
    if (NEWS_RE.search(text) or (SAFETY_ASK_RE.search(text) and not PLAN_RE.search(text))) and not (in_plan and MODIFY_RE.search(text)):
        return "news"
    has_days = bool(re.search(r"\d+\s*박|\d+\s*일", text))
    if COURSE_LIST_RE.search(text) and not has_days:
        return "course"  # '추천 여행코스' 목록 (일정을 짜달라는 '코스'와 구분)
    list_ok = bool(ASK_RE.search(text)) if (mid or in_plan) else True
    # "2박3일로 부산 여행을 가는데 일정이 비어서 축제 찾아줘": 축제 목록만이 아니라 일정을 짜고 축제 후보를 함께 보여준다
    trip_ctx = bool(FEST_TRIP_RE.search(text)) and (has_days or mid or in_plan)
    if (FEST_RE.search(text) and not FEST_PLAN_RE.search(text) and not (in_plan and MODIFY_RE.search(text)) and not (trip_ctx and not in_plan)
            and (list_ok or bool(FEST_ASK_RE.search(text)))):
        # 축제를 물으면 날짜·기간이 함께 있어도 축제 목록 ("부산 2박3일 축제 추천해줘", "축제 일정 알려줘").
        # "축제 위주로 일정 짜줘"처럼 짜달라는 말이 있으면 일정
        return "festival"
    if PLAN_RE.search(text) or (in_plan and MODIFY_RE.search(text)):
        return "plan"
    if is_place_info_request(text):  # "OO식당 정보 알려줘", "XX공원 어떤 곳이야?" → 그 장소만 답한다 (추천 아님)
        return "place_info"
    if list_ok and STAY_RE.search(text):
        return "stay"
    if list_ok and FEST_RE.search(text):
        return "festival"
    if list_ok and FOOD_RE.search(text):
        return "food"
    if list_ok and RECO_RE.search(text):
        return "recommend"
    return "plan"


def _answer_list(session: "ChatSession", text: str, intent: str, today: date, ranker,
                 region: tuple[str, str] | None = None) -> tuple[str, dict, list[str]]:
    """일정 없이 지역만으로 답하는 단발 추천(여행지·맛집·숙박·축제·여행코스). 이미 만든 일정이 있어도 건드리지 않는다."""
    set_progress("추천할 곳을 찾고 있어요")
    s = session.slots
    if region:
        sido, area = region
    else:
        sido, area = resolve_place_ext(text)
        if not sido:
            sido, area = s["region"], s["area"]  # 이전 대화의 지역
    if not sido:
        return "어느 지역을 찾아드릴까요? (예: 성남, 분당, 부산 해운대)", {}, []
    if not s["region"]:
        s["region"], s["area"] = sido, area  # 이후 일정 요청에서 재사용
    if intent in ("stay", "course"):
        places, warnings = _collect_type(sido, area, "32" if intent == "stay" else "25")
    elif intent == "festival":
        f_start, f_end, dated = _festival_range(session, text, today, sido)
        places, warnings = _collect_festivals(sido, area, f_start, f_end)
    else:
        places, warnings = _collect_candidates(sido, today, today, True, area)
    label = area or sido
    if intent == "festival" and dated:
        label += f" ({fmt_md(f_start)}" + (f" ~ {fmt_md(f_end)})" if f_end != f_start else ")")
    query = " ".join(x for x in [sido, area, text] if x)
    reply, views, w = answer_list(intent, label, text, places, lambda pool: rank_places(pool, sido, query, ranker),
                                  enrich, lambda items: enrich_intro(items, 12))
    if intent == "festival" and views:
        shown = {v["name"] for v in views}
        session.last_festivals = [p for p in places if p["title"] in shown]  # "저거 기준으로 다시 짜줘"에 쓴다
    if intent == "festival" and not views:
        when = label[len(area or sido):].strip() or f"앞으로 {FEST_DAYS_AHEAD}일 안"
        reply = f"{area or sido}에서 {when}에 열리는 축제·행사를 찾지 못했어요. 날짜나 지역을 바꿔서 다시 물어봐 주세요."
    return reply, {"intent": intent, "places": views}, warnings + w


def _festival_range(session: "ChatSession", text: str, today: date, sido: str) -> tuple[date, date, bool]:
    """
    축제를 찾을 기간 (시작, 끝, 날짜를 특정했는지).
    - 말한 날짜·기간: "10월 10일 축제", "이번 주말 축제", "10월 10일부터 2박3일 축제"
    - 달만 말함: "11월 축제" → 그 달 전체 (오늘 이전은 제외)
    - "이 기간", "여행 때" 또는 같은 지역 일정이 이미 있으면 그 여행 날짜
    - 아무것도 없으면 오늘부터 FEST_DAYS_AHEAD일
    """
    rd = parse_trip_dates(text, today)
    if rd["start"]:
        start = rd["start"]
        end = rd["end"] or (start + timedelta(days=rd["nights"]) if rd["nights"] is not None else start)
        return start, end, True
    if m := MONTH_ONLY_RE.search(text):
        month = int(m.group(1))
        if 1 <= month <= 12:
            year = today.year + (1 if month < today.month else 0)
            first = date(year, month, 1)
            last = (date(year + (month == 12), month % 12 + 1, 1) - timedelta(days=1))
            return max(first, today), last, True
    s = session.slots
    ss, se = parse_iso(s["start_date"]), parse_iso(s["end_date"])
    if ss and se and se >= today and s["region"] == sido and (PERIOD_REF_RE.search(text) or session.plan is not None):
        return max(ss, today), se, True
    return today, today + timedelta(days=FEST_DAYS_AHEAD), False


def _multi_region_reply(session: "ChatSession", text: str, intent: str, regs: list[tuple[str, str]], today: date, ranker):
    """여러 지역을 한 번에 물으면 지역마다 독립된 답변을 만들어 구분선으로 나눈다."""
    replies, views, warnings = [], [], []
    for reg in regs:
        r, extra, w = _answer_list(session, text, intent, today, ranker, region=reg)
        replies.append(r)
        views += extra.get("places") or []
        warnings += w
    return "\n\n---\n\n".join(replies), {"intent": intent, "places": views}, warnings


# ── 다중 지역 일정 (대구 1박2일, 부산 2박3일) ─────────────────────────────
def _trip_label(t: dict) -> str:
    return t["area"] or t["sido"]


def _multi_intro(trips: list[dict]) -> str:
    return ", ".join(f"{_trip_label(t)} {t['nights']}박 {t['nights'] + 1}일" if t["nights"] else f"{_trip_label(t)} 당일" for t in trips)


def _start_multi(session: ChatSession, trips: list[dict], text: str, today: date, ranker) -> dict:
    """지역별 기간이 있는 일정 요청. 출발일을 알면 바로 만들고, 모르면 한 번만 되묻는다."""
    # 이전 지역의 데이터는 모두 버린다
    session.plan = session.view = session.raw = session.raw_key = None
    session.last_cand_map, session.id_map, session.trips = {}, {}, {}
    party = _heuristic_party(text)
    extra = _leftover(text, today)
    session.pending_multi = {"trips": trips, "party": party, "preferences": _clip(extra, 60) if len(extra) >= 6 else ""}
    start = parse_trip_dates(text, today)["start"]
    if start is None:
        reply = f"{_multi_intro(trips)} 일정이군요. 지역별로 각각 만들어 드릴게요. 언제 출발하시나요? (예: 10월 10일, 이번 주말, 내일)"
        session.history.append({"role": "assistant", "content": reply})
        return _pack(session, "asking", reply)
    return _generate_multi(session, start, text, today, ranker)


def _generate_multi(session: ChatSession, start: date, text: str, today: date, ranker) -> dict:
    pending = session.pending_multi
    if start < today:
        reply = f"말씀하신 날짜가 이미 지났어요. 오늘({fmt_korean(today)}) 이후 날짜로 다시 알려주시겠어요?"
        session.history.append({"role": "assistant", "content": reply})
        return _pack(session, "asking", reply)
    trips, d = pending["trips"], start
    for t in trips:
        if t["nights"] + 1 > MAX_TRIP_DAYS:
            reply = f"한 번에 최대 {MAX_TRIP_DAYS}일까지 일정을 짜드릴 수 있어요. 기간을 줄여서 다시 알려주시겠어요?"
            session.history.append({"role": "assistant", "content": reply})
            return _pack(session, "asking", reply)
    replies, subs, warnings = [], {}, []
    for t in trips:  # 지역마다 독립된 하위 세션으로 만든다 (서로의 데이터가 섞이지 않음)
        end = d + timedelta(days=t["nights"])
        sub = ChatSession()
        sub.slots.update(region=t["sido"], area=t["area"], start_date=d.isoformat(), end_date=end.isoformat(), nights=t["nights"],
                         party=pending["party"], preferences=pending["preferences"])
        sub.asked_optional = True
        replies.append(_make_plan(sub, text, today, ranker, False, warnings))
        subs[_trip_label(t)] = sub
        d = end + timedelta(days=1)  # 다음 지역은 다음 날부터
    session.trips, session.pending_multi, session.plan = subs, None, None
    first = next(iter(subs.values()))
    session.slots = dict(first.slots)
    session.view = {
        "trips": [{"region": label, "sido": sub.slots["region"], "area": sub.slots["area"],
                   "start_date": sub.slots["start_date"], "end_date": sub.slots["end_date"],
                   "plan": (sub.view or {}).get("plan"), "conditions": (sub.view or {}).get("conditions"),
                   "risks": (sub.view or {}).get("risks", [])} for label, sub in subs.items()],
        "caveats": list(dict.fromkeys(c for sub in subs.values() for c in (sub.view or {}).get("caveats", []))),
        # 지역별 품질 지표 (하위 세션에서 꺼내 두어야 나중 응답에 다시 실리지 않는다)
        "evaluation": {"regions": {label: (sub.view or {}).pop("evaluation", None) for label, sub in subs.items()}},
    }
    reply = "\n\n---\n\n".join(replies)
    session.history.append({"role": "assistant", "content": reply})
    return _pack(session, "planned", reply)


def _continue_multi(session: ChatSession, text: str, today: date, ranker) -> dict | None:
    """출발일을 기다리는 중의 다음 메시지. 날짜가 있으면 만들고, 다른 지역 요청이면 기다리던 것을 버린다."""
    pending = session.pending_multi
    known = {(t["sido"]) for t in pending["trips"]}
    regs = regions_ext(text)
    if regs and any(sido not in known for sido, _ in regs):
        session.pending_multi = None  # 새 지역을 말했으므로 이전 요청은 초기화
        return None
    party = _heuristic_party(text)
    if party:
        pending["party"] = party
    start = parse_trip_dates(text, today)["start"]
    if start is None:
        reply = f"{_multi_intro(pending['trips'])} 일정의 출발일을 알려주세요. (예: 10월 10일, 이번 주말, 내일)"
        session.history.append({"role": "assistant", "content": reply})
        return _pack(session, "asking", reply)
    return _generate_multi(session, start, text, today, ranker)


def _route_trip(session: ChatSession, text: str, today: date, ranker) -> dict | None:
    """다중 지역 일정이 있을 때: 말한 지역의 일정으로 보내고, 새 지역이면 이전 다중 일정을 초기화한다."""
    regs = regions_ext(text)
    for sido, area in regs:
        for sub in session.trips.values():
            if sub.slots["region"] == sido and (not area or not sub.slots["area"] or area == sub.slots["area"]):
                res = _handle_message(sub, text, today, ranker)
                session.history.append({"role": "assistant", "content": res["reply"].split(FOOTER_TITLE)[0].rstrip("-\n ")})
                return {**res, "session_id": session.session_id}
    if regs:
        session.trips = {}  # 새 지역: 이전 다중 일정은 버리고 일반 흐름으로
        return None
    reply = f"어느 지역 일정을 말씀하시나요? ({' / '.join(session.trips)})"
    session.history.append({"role": "assistant", "content": reply})
    return _pack(session, "planned", reply)


# ── 진입점 ────────────────────────────────────────────────────────────
def _pack(session: ChatSession, stage: str, reply: str, extra_caveats: list[str] | None = None,
          extra: dict | None = None, replace_caveats: bool = False, with_footer: bool = True) -> dict:
    view = session.view or {}
    evaluation = view.pop("evaluation", None)
    caveats = [] if replace_caveats else list(view.get("caveats", []))
    for c in extra_caveats or []:
        if c not in caveats:
            caveats.insert(0, c)
    result = {
        "session_id": session.session_id, "stage": stage, "reply": reply + (FOOTER if with_footer else ""),
        "slots": dict(session.slots), "missing": _missing(session.slots),
        "plan": view.get("plan"), "conditions": view.get("conditions"), "risks": view.get("risks", []),
        "caveats": caveats, "used_sources": view.get("used_sources", []),
        "timings": view.get("timings"), "llm_stats": view.get("llm_stats"), "evaluation": evaluation,
        "intent": "plan", "places": None, "news": None, "place": None, "trips": view.get("trips"),
        **(extra or {}),
    }
    return result


def handle_message(session: ChatSession, text: str, today: date | None = None, ranker=None, debug: bool = False) -> dict:
    """
    사용자 메시지 한 건을 처리하고 챗봇 응답을 돌려줍니다.

    Returns:
        {"session_id", "stage": "asking"|"planned", "reply"(마크다운), "slots", "missing",
         "plan"(일자별 구조), "conditions"(일자별 날씨·미세먼지), "risks", "caveats", "used_sources"}
    LLM이나 외부 API가 실패해도 예외를 던지지 않고, 가능한 범위에서 응답하며 caveats에 사유를 남깁니다.
    debug=True 이면 DEV_MODE 가 꺼져 있어도 이 응답에만 caveats·timings·llm_stats 를 싣습니다 (관리자 화면용).
    """
    if not (text or "").strip() or getattr(_turn_ctx, "cur", None):  # 인사말 요청·하위 세션은 취소 대상이 아니다
        result = _handle_message(session, text, today, ranker)
    else:
        result = _handle_turn(session, text, today, ranker)
        if result is None:
            return _cancelled_reply(session)
    ack = _user_place_ack(session)  # 이번 메시지에서 읽은 숙소·장소 (일정을 새로 만들 때 반영된 뒤 요약해서 보여줌)
    if ack:
        result["reply"] = ack + result["reply"]
    if not (DEV_MODE or debug):  # 서비스에서는 API 오류·제약사항·소요 시간 같은 내부 정보를 응답에 싣지 않는다
        result.update(caveats=[], timings=None, llm_stats=None, evaluation=None)
    return result


def _handle_turn(session: ChatSession, text: str, today: date | None, ranker) -> dict | None:
    """말 한 건을 취소할 수 있게 처리한다. 취소됐으면 대화 기억을 되돌리고 None."""
    with session.lock:
        with session.turn_lock:
            session.turn += 1
            my = session.busy_turn = session.turn
            session.progress, session.progress_at = "말씀을 이해하고 있어요", time.time()
            if time.time() < session.cancel_next_until:  # 이 말의 취소가 먼저 와 있었다
                session.cancel_next_until = 0.0
                session.busy_turn = None
                return None
        snap = _snapshot(session)
        _turn_ctx.cur = (session, my)
        result = None
        try:
            result = _handle_message(session, text, today, ranker)
        except TurnCancelled:
            pass
        finally:
            _turn_ctx.cur = None
            with session.turn_lock:
                session.busy_turn = None
                session.progress = ""
                cancelled = session.cancelled_turn == my
                session.undo = None if cancelled else (my, snap, time.time())
        if cancelled:
            _restore(session, snap)
            return None
        return result


def _cancelled_reply(session: ChatSession) -> dict:
    out = _pack(session, "planned" if session.plan or session.trips else "asking", "보낸 말을 취소했어요.", with_footer=False)
    out["cancelled"] = True
    return out


def _handle_message(session: ChatSession, text: str, today: date | None, ranker) -> dict:
    today = today or date.today()
    text = (text or "").strip()
    with session.lock:
        session.last_used = time.time()
        if not text:
            reply = GREETING if not session.history else "메시지를 입력해 주세요."
            return _pack(session, "planned" if session.plan or session.trips else "asking", reply, with_footer=False)
        if RESET_RE.search(text):
            session.reset()
            return _pack(session, "asking", "좋아요, 처음부터 다시 시작할게요!\n\n" + GREETING)

        session.history.append({"role": "user", "content": text})
        session.rest_text = None
        stay, rest = parse_stay_times(text)  # "체크인 오후 3시, 체크아웃 11시" → 숙소 시각. 이 표현은 지역·날짜·취향 읽기에 넘기지 않는다
        if stay:
            session.stay_times, session.asked_stay_times = {**session.stay_times, **stay}, True
            session.pending_stay = {**(session.pending_stay or {}), **stay}
            text = rest
            if not rest:
                if session.plan and session.view:
                    reply = _rerender(session)
                    session.history.append({"role": "assistant", "content": reply})
                    return _pack(session, "planned", _user_place_ack(session) + reply)
                if session.asked_optional:
                    text = "상관없어요"  # 시각만 말했으면 동행·취향은 따로 없다는 뜻
                else:
                    reply = _user_place_ack(session).rstrip() + "\n\n여행 지역과 날짜를 알려주시면 반영해서 일정을 짜 드릴게요."
                    session.history.append({"role": "assistant", "content": reply})
                    return _pack(session, "asking", reply)
        res = _try_festival_add(session, text)  # 추천받은 축제 "1번 2일차에 추가해줘" → 일정에 넣고 그날 나머지를 축제장 주변으로 다시 맞춤 (장소 말보다 먼저)
        if res is not None:
            return res
        res = _try_user_places(session, text)  # "숙소는 OO호텔, 2일차 12시에 OO카페 들를게" → 숙소·고정 장소 반영
        if res is not None:
            return res
        if session.rest_text is not None:  # 장소로 읽은 문장을 뺀 나머지만 아래 일반 흐름(지역·날짜·취향 읽기)에 넘긴다
            text, session.rest_text = session.rest_text, None
        res = _try_festival_time(session, text)  # "불꽃축제 저녁 7시부터 9시" → 그 시간에 맞춰 다시 조율
        if res is not None:
            return res
        intent = detect_intent(text, session)
        if intent in ("plan", "festival") and FEST_RE.search(text) and FEST_RECO_RE.search(text) and not FEST_FOCUS_RE.search(text):
            # "둘째 날이 비어서 괜찮은 축제 찾아줘": 후보만 보여주고, 어느 날에 넣을지 기억해 둔다
            days = _target_days(text, 60)
            session.fest_hint_day = days[0] if days else None
            session.want_fest_reco = session.want_fest_reco or intent == "plan"  # 다음 답("상관없어요")에서 일정을 만들 때까지 기억
        if intent == "about":
            session.history.append({"role": "assistant", "content": ABOUT_REPLY})
            return _pack(session, "planned" if session.plan else "asking", ABOUT_REPLY, None, {"intent": "about"}, replace_caveats=True)
        if intent == "plan":
            trips = parse_multi_trips(text, _last_region)  # "대구 1박2일, 부산 2박3일" → 지역별 독립 일정
            if trips:
                return _start_multi(session, trips, text, today, ranker)
            if session.pending_multi:
                res = _continue_multi(session, text, today, ranker)
                if res is not None:
                    return res
            if session.trips:
                res = _route_trip(session, text, today, ranker)
                if res is not None:
                    return res
        stage_now = "planned" if session.plan or session.trips else "asking"
        if intent == "place_info":
            set_progress("장소 정보를 찾고 있어요")
            reply, extra, w = answer_place(text)
            session.history.append({"role": "assistant", "content": reply})
            return _pack(session, stage_now, reply, w, extra, replace_caveats=True)
        if intent == "news":
            req, regs = parse_news_request(text), regions_ext(text)
            if (not req["target"] or req["safety"]) and len(regs) >= 2:  # 여러 지역 소식은 지역별로 따로
                parts, warns = [], []
                for sido, area in regs:
                    r, _ex, w, _ask = answer_news(f"{area or sido} {'범죄 ' if req['safety'] else ''}소식", (sido, area))
                    parts.append(r)
                    warns += w
                reply, extra, w = "\n\n---\n\n".join(parts), {"intent": "news", "news": None}, warns
            else:
                scope = regs[-1] if (regs and not req["sido"]) else (session.slots["region"] or None, session.slots["area"])
                set_progress("최근 소식을 찾고 있어요")
                reply, extra, w, _ask = answer_news(text, scope)
            session.history.append({"role": "assistant", "content": reply})
            return _pack(session, stage_now, reply, w, extra, replace_caveats=True)
        if intent in LIST_INTENTS:
            regs = regions_ext(text)
            if len(regs) >= 2:  # 여러 지역은 지역마다 독립된 답변
                reply, extra, w = _multi_region_reply(session, text, intent, regs, today, ranker)
            else:
                reply, extra, w = _answer_list(session, text, intent, today, ranker)
            session.history.append({"role": "assistant", "content": reply})
            return _pack(session, stage_now, reply, w, extra, replace_caveats=True)
        warnings: list[str] = []
        in_plan = session.plan is not None
        before = _trip_key(session.slots)

        use_llm = CHAT_EXTRACT_LLM_MIN_CHARS == 0 or (not in_plan and len(text) >= CHAT_EXTRACT_LLM_MIN_CHARS)
        llm = _llm_extract(session, text, today, warnings) if use_llm else None
        issues = _apply_extraction(session, text, llm, today, in_plan, skipped=not use_llm)
        changed = _trip_key(session.slots) != before
        missing = _missing(session.slots)
        s = session.slots

        if issues:
            reply = _issue_message(issues, today, text)
            asked_region = bool({"ambiguous_region", "province_group"} & set(issues))
            if missing and not (asked_region and missing[0] == "region"):  # 지역은 방금 되물었으니 또 묻지 않는다
                reply += "\n\n" + _ask_missing(s)
            stage = "planned" if in_plan else "asking"
        elif missing:
            reply, stage = _ask_missing(s), "asking"
        elif session.lodging_hold and not session.plan:
            reply, stage = _lodging_hold_reply(session), "asking"
        elif not session.plan and not session.asked_optional and not (s["party"] or s["preferences"]):
            session.asked_optional = True
            reply, stage = _ask_optional(s), "asking"
        else:
            session.asked_optional = True
            reply = _make_plan(session, text, today, ranker, refine=in_plan and not changed, warnings=warnings)
            stage = "planned" if session.plan else "asking"

        session.history.append({"role": "assistant", "content": reply})
        return _pack(session, stage, reply, warnings if stage == "asking" else None)
