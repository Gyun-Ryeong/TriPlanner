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
import json
import re
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import date, timedelta

from config import (
    DEV_MODE, CHAT_EXTRACT_LLM_MIN_CHARS, CHAT_HISTORY_TURNS, CHAT_MAX_CANDIDATES, CHAT_MAX_NEWS, CONTEXT_TTL_SEC,
    MAX_TRIP_DAYS, NEWS_DAYS_BACK,
)
from collectors.tourism import enrich_intro
from llm.ollama_client import LAST_STATS, chat_json_messages
from travel.conditions import build_day_conditions, display_line, prompt_line
from travel.context import enrich, gather_raw, rank_places, select_candidates
from travel.dates import WD, fmt_korean, parse_iso, parse_trip_dates
from travel.geo import _coord, district_of
from travel.gazetteer import lookup_regions
from travel.lists import answer_list
from travel.places import SIGHT_TYPES
from travel.news import NEWS_RE, answer_news, parse_news_request
from travel.placeinfo import answer_place, is_place_info_request
from travel.multi import parse_multi_trips
from travel.pipeline import FORECAST_DAYS, _collect_candidates, _collect_festivals, _collect_type, wants_food
from travel.planner import (
    PLAN_SYSTEM_PROMPT, build_plan_user_message, fallback_plan, hydrate_plan, normalize_plan, render_markdown,
)
from travel.regions import SIDO, _mentions, mentioned_regions, resolve_place

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
RECO_RE = re.compile(r"추천|가볼\s*만한|가볼만한|명소|관광지|볼거리|놀거리|구경|데이트\s*장소|갈\s*만한|핫플|여행지")
ASK_RE = re.compile(r"알려|추천|보여|찾아|어디|뭐\s*있|뭐가\s*있|있을까|가볼|\?")
STAY_RE = re.compile(r"숙박|숙소|호텔|펜션|리조트|모텔|게스트하우스|한옥\s*스테이|민박|묵을|잘\s*곳")
FEST_RE = re.compile(r"축제|행사|공연|페스티벌|이벤트")
COURSE_LIST_RE = re.compile(r"추천\s*여행\s*코스|추천\s*코스|여행\s*코스\s*(목록|리스트)|코스\s*(목록|리스트)")
LIST_INTENTS = ("recommend", "food", "stay", "festival", "course")
MODIFY_RE = re.compile(r"넣어|추가|바꿔|빼|변경|수정|교체|대신|다시|늘려|줄여")

CHANGE_RE = re.compile(r"(바꿔|바꾸|변경|옮겨|미뤄|당겨|출발|떠나|말고|대신|로 갈|으로 갈|로 가|으로 가|갈래|가고 싶|다시 짜|새로)")
DATE_HINT_RE = re.compile(r"\d|오늘|내일|모레|글피|주말|다음|이번|담주|요일|당일|이틀|사흘|나흘")
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
            "party": "", "preferences": "", "avoid": ""}


def regions_ext(text: str) -> list[tuple[str, str]]:
    """문장 속 지역을 등장 순서대로. 도시 목록에 없는 기초지자체(곡성, 영월 등)는 시군구 사전으로 보충한다."""
    return mentioned_regions(text) or lookup_regions(text)


def resolve_place_ext(text: str) -> tuple[str | None, str]:
    sido, area = resolve_place(text)
    if sido:
        return sido, area
    found = lookup_regions(text)
    return found[-1] if found else (None, "")


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
    last_used: float = field(default_factory=time.time)
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def reset(self) -> None:
        self.slots, self.history = _empty_slots(), []
        self.raw = self.raw_key = self.plan = self.view = None
        self.last_cand_map, self.id_map, self.asked_optional = {}, {}, False
        self.trips, self.pending_multi = {}, None


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
    work = parse_trip_dates(text, today)["rest"]  # 날짜 표현은 이미 공백으로 지워짐 (길이 유지)
    for a, b, *_ in _mentions(text):
        work = work[:a] + " " * (b - a) + work[b:]
    work = re.sub(r"\d{1,2}\s*박(?:\s*\d{1,2}\s*일)?|당일치기|당일|\d{1,2}\s*일\s*(?:간|동안|일정|여행|코스)|이틀|사흘|나흘", " ", work)
    return re.sub(r"\s+", " ", work).strip()


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
        parsed, _ = chat_json_messages(
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
    # 일정이 나온 뒤에는 '바꿔줘/갈래' 같은 변경 의도가 있거나 '이전과 다른 새 지역'을 말했을 때만 지역·날짜를 바꾼다
    # (예: "내일 비 와?"라고 물었다고 출발일이 바뀌면 안 되지만, 새 지역을 말하면 이전 지역 데이터는 버린다)
    explicit_new_region = bool(sido) and (sido != s["region"] or bool(area and area != s["area"]))
    allow_change = (not in_plan) or bool(CHANGE_RE.search(text)) or explicit_new_region
    if not sido:
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
            if e_new:
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
        return f"{_label(s)} 좋아요! {extra}언제 출발하시나요? (예: 10월 10일, 이번 주말, 내일)"
    return f"{_label(s)}, {_date_phrase(s)}이군요. 몇 박 며칠로 다녀오실 예정인가요? (예: 2박 3일, 당일치기)"


def _ask_optional(s: dict) -> str:
    return (
        f"{_label(s)}, {_date_phrase(s)} 일정이네요! 더 잘 맞는 일정을 짜드리려고 하나만 여쭤볼게요.\n"
        "누구와 함께 가시나요? 그리고 원하는 분위기(예: 조용한 바다, 맛집 위주, 사진 명소, 아이와 함께)가 있으면 알려주세요.\n"
        "특별한 건 없으면 \"상관없어요\"라고 해주세요."
    )


def _issue_message(issues: list[str], today: date) -> str:
    msgs = {
        "past_date": f"말씀하신 날짜가 이미 지났어요. 오늘({fmt_korean(today)}) 이후 날짜로 다시 알려주시겠어요?",
        "bad_range": "도착일이 출발일보다 빠르네요. 날짜를 다시 알려주시겠어요?",
        "too_long": f"한 번에 최대 {MAX_TRIP_DAYS}일까지 일정을 짜드릴 수 있어요. 기간을 줄여서 다시 알려주시겠어요?",
        "unknown_region": "아직 지원하지 않는 지역이에요. 가능한 지역: " + ", ".join(SIDO),
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
        session.raw = gather_raw(sido, area, start, end, include_food, today)
        session.raw_key = key
    raw = session.raw
    t_gathered = time.perf_counter()

    # 2) 일자별 컨디션 (날씨·미세먼지)
    dates = [(start + timedelta(days=i)).isoformat() for i in range((end - start).days + 1)]
    conditions = build_day_conditions(start, end, raw["weather"], raw["air"]["by_date"])
    bad_days = sum(1 for c in conditions if c["outdoor_ok"] is False)

    sights = [p for p in raw["places"] if p["content_type_id"] in SIGHT_TYPES]
    eateries = [p for p in raw["places"] if p["content_type_id"] == "39"]

    if not sights:
        # 후보가 하나도 없으면 빈 일정을 만들지 않는다. 다음 요청에서 다시 수집하도록 캐시도 비운다.
        session.raw = session.raw_key = None
        session.view = {"plan": None, "conditions": conditions, "risks": [], "used_sources": [],
                        "caveats": _caveats(raw, conditions, warnings, start, end, today)}
        return f"지금은 {area or sido} 일정에 넣을 장소를 찾지 못했어요. 잠시 뒤에 다시 말씀해 주시거나 다른 지역으로 알려주세요."

    # 3) 후보 선별: 취향과 유사한 순 + 궂은 날을 위한 실내 후보 보장
    query = " ".join(x for x in [sido, area, s["party"], s["preferences"], text if refine else ""] if x)
    ranked = rank_places(sights, sido, query, ranker)
    restaurants = rank_places(eateries, sido, query, ranker)[:30]  # 식사 장소 후보 (취향 유사도 상위)
    wants_activity = bool(ACTIVITY_RE.search(f"{s['preferences']} {text}"))
    caps = {} if wants_activity else {"28": 3}  # 액티비티를 원한다고 하지 않았으면 레포츠가 후보를 독차지하지 않게
    chosen = select_candidates(ranked, max(6, min(CHAT_MAX_CANDIDATES, len(dates) * 4 + 4)),
                               min(2 * bad_days + 1, 8) if bad_days else 0, caps)
    if refine and session.last_cand_map:  # 수정 요청일 때 기존 일정의 장소는 계속 후보에 포함
        keys = {(p["content_id"] or p["title"]) for p in chosen}
        chosen += [p for p in session.last_cand_map.values() if (p["content_id"] or p["title"]) not in keys]
    warnings += enrich(chosen)

    def cid_of(p):
        k = p["content_id"] or p["title"]
        if k not in session.id_map:
            session.id_map[k] = f"C{len(session.id_map) + 1}"
        return session.id_map[k]

    cand_map = {cid_of(p): p for p in chosen}
    news_by_id = {n["id"]: n for n in raw["news"]}

    # 4) LLM 일정 생성/수정
    mode = "수정" if refine and session.plan else "새 일정"
    user_msg = build_plan_user_message(
        mode=mode, region_label=_label(s), start=s["start_date"], end=s["end_date"], n_days=len(dates),
        party=s["party"], preferences=s["preferences"], avoid=s["avoid"],
        condition_lines=[prompt_line(c) for c in conditions],
        candidate_lines=[_cand_line(cid, p, news_by_id) for cid, p in cand_map.items()],
        news_lines=[f"{n['id']} | [{n['category']}] {n['pub_date']} | {n['title']} | {n['description'][:100]}" for n in raw["news"][:CHAT_MAX_NEWS]],
        current_plan_text=_plan_text(session.plan, session.last_cand_map, dates) if mode == "수정" else "",
        user_request=text,
    )
    t_ranked = time.perf_counter()
    parsed, raw_txt, llm_error = None, "", False
    try:
        parsed, raw_txt = chat_json_messages(
            [{"role": "system", "content": PLAN_SYSTEM_PROMPT}, *_history_for_llm(session), {"role": "user", "content": user_msg}],
            temperature=0.4,
        )
    except Exception as e:
        llm_error = True
        warnings.append(f"AI 연결 문제로 일정 생성/수정을 하지 못했어요 ({type(e).__name__}: {str(e)[:500]})")
    t_llm_done = time.perf_counter()
    llm_stats = dict(LAST_STATS)
    plan, w = normalize_plan(parsed, cand_map, dates)
    warnings += w
    if not llm_error and plan is None:
        # 오류 없이 응답했는데 못 쓰는 경우: 무슨 응답이었는지 보여준다 (원인 파악용)
        if not raw_txt.strip():
            warnings.append("AI가 빈 응답을 돌려줬어요. 모델이 '생각'만 하고 답을 못 냈을 수 있어요 (.env에 OLLAMA_THINK=false 를 넣어보세요).")
        elif parsed is None:
            warnings.append(f"AI 응답을 JSON으로 읽지 못했어요 (응답 앞부분: {raw_txt[:100]!r})")
        else:
            warnings.append("AI 응답에 쓸 수 있는 일정이 없었어요 (장소 id를 맞추지 못했을 수 있어요).")
    if plan is not None and plan["days"] is None and mode == "새 일정":
        plan = None  # 새 일정인데 days가 없으면 실패로 간주

    if plan is None and mode == "수정":
        # 수정 실패: 기존 일정은 그대로 두고 알려준다
        if not llm_error:
            warnings.append("AI 응답을 이해하지 못해 일정을 바꾸지 못했어요.")
        session.view = {**(session.view or {}), "caveats": _caveats(raw, conditions, warnings, start, end, today)}
        return "죄송해요, 지금은 요청하신 수정을 반영하지 못했어요. 잠시 후 다시 말씀해 주시거나 표현을 바꿔서 알려주세요."
    if plan is None:
        order = list(cand_map)  # cand_map은 순위순
        if not ACTIVITY_RE.search(f"{s['preferences']} {text}"):
            # 액티비티를 원한다고 하지 않았으면 레포츠(28)는 뒤로 (순위는 그대로 유지)
            order.sort(key=lambda cid: str(cand_map[cid].get("content_type_id")) == "28")
        plan = fallback_plan(dates, conditions, order, cand_map)
        warnings.append("AI 일정 대신 규칙 기반 기본 일정을 보여드려요.")

    if plan["days"] is None:  # 질문·감사 등: 일정은 그대로, 답만 한다
        reply = plan["message"]
        session.view = {**(session.view or {}), "caveats": _caveats(raw, conditions, warnings, start, end, today)}
        return reply

    # 5) 구조화 + 렌더링
    session.plan, session.last_cand_map = plan, {cid: p for cid, p in cand_map.items()}
    days_view = hydrate_plan(plan, cand_map, conditions, restaurants)
    # 일정을 물었으니 일정만 답한다 (뉴스·마무리 질문 같은 묻지 않은 내용은 붙이지 않음. 뉴스는 risks 필드에만 남김)
    reply = render_markdown(plan["message"], days_view, conditions, "", [], place_label=area or sido)

    sources = ["tourism"]
    if raw["news"]:
        sources.append("naver_news")
    if raw["weather"]:
        sources.append("weather")
    if raw["air"]["by_date"]:
        sources.append("air_quality")
    session.view = {
        "timings": {"collect_sec": round(t_gathered - t_start, 1), "rank_sec": round(t_ranked - t_gathered, 1),
                    "llm_sec": round(t_llm_done - t_ranked, 1), "tasks": raw.get("timings", {})},
        "llm_stats": llm_stats,
        "plan": days_view, "conditions": conditions, "used_sources": sources,
        "risks": [{"category": n["category"], "title": n["title"], "link": n["link"], "pub_date": n["pub_date"]} for n in raw["news"]],
        "caveats": _caveats(raw, conditions, warnings, start, end, today),
    }
    return reply


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
    if NEWS_RE.search(text) and not (in_plan and MODIFY_RE.search(text)):
        return "news"
    has_days = bool(re.search(r"\d+\s*박|\d+\s*일", text))
    if COURSE_LIST_RE.search(text) and not has_days:
        return "course"  # '추천 여행코스' 목록 (일정을 짜달라는 '코스'와 구분)
    if FEST_RE.search(text) and re.search(r"일정|스케줄", text) and not re.search(r"짜|계획|코스", text):
        return "festival"  # "축제 일정 알려줘" = 축제 목록
    if PLAN_RE.search(text) or (in_plan and MODIFY_RE.search(text)):
        return "plan"
    if is_place_info_request(text):  # "OO식당 정보 알려줘", "XX공원 어떤 곳이야?" → 그 장소만 답한다 (추천 아님)
        return "place_info"
    list_ok = bool(ASK_RE.search(text)) if (mid or in_plan) else True
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
        places, warnings = _collect_festivals(sido, area, today, today + timedelta(days=60))
    else:
        places, warnings = _collect_candidates(sido, today, today, True, area)
    query = " ".join(x for x in [sido, area, text] if x)
    reply, views, w = answer_list(intent, area or sido, text, places, lambda pool: rank_places(pool, sido, query, ranker),
                                  enrich, lambda items: enrich_intro(items, 12))
    return reply, {"intent": intent, "places": views}, warnings + w


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
        "trips": [{"region": label, "plan": (sub.view or {}).get("plan"), "conditions": (sub.view or {}).get("conditions"),
                   "risks": (sub.view or {}).get("risks", [])} for label, sub in subs.items()],
        "caveats": list(dict.fromkeys(c for sub in subs.values() for c in (sub.view or {}).get("caveats", []))),
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
                res = handle_message(sub, text, today, ranker)
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
    caveats = [] if replace_caveats else list(view.get("caveats", []))
    for c in extra_caveats or []:
        if c not in caveats:
            caveats.insert(0, c)
    result = {
        "session_id": session.session_id, "stage": stage, "reply": reply + (FOOTER if with_footer else ""),
        "slots": dict(session.slots), "missing": _missing(session.slots),
        "plan": view.get("plan"), "conditions": view.get("conditions"), "risks": view.get("risks", []),
        "caveats": caveats, "used_sources": view.get("used_sources", []),
        "timings": view.get("timings"), "llm_stats": view.get("llm_stats"),
        "intent": "plan", "places": None, "news": None, "place": None, "trips": view.get("trips"),
        **(extra or {}),
    }
    if not DEV_MODE:  # 서비스에서는 API 오류·제약사항·소요 시간 같은 내부 정보를 응답에 싣지 않는다
        result.update(caveats=[], timings=None, llm_stats=None)
    return result


def handle_message(session: ChatSession, text: str, today: date | None = None, ranker=None) -> dict:
    """
    사용자 메시지 한 건을 처리하고 챗봇 응답을 돌려줍니다.

    Returns:
        {"session_id", "stage": "asking"|"planned", "reply"(마크다운), "slots", "missing",
         "plan"(일자별 구조), "conditions"(일자별 날씨·미세먼지), "risks", "caveats", "used_sources"}
    LLM이나 외부 API가 실패해도 예외를 던지지 않고, 가능한 범위에서 응답하며 caveats에 사유를 남깁니다.
    """
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
        intent = detect_intent(text, session)
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
            reply, extra, w = answer_place(text)
            session.history.append({"role": "assistant", "content": reply})
            return _pack(session, stage_now, reply, w, extra, replace_caveats=True)
        if intent == "news":
            req, regs = parse_news_request(text), regions_ext(text)
            if not req["target"] and len(regs) >= 2:  # 여러 지역 소식은 지역별로 따로
                parts, warns = [], []
                for sido, area in regs:
                    r, _ex, w, _ask = answer_news(f"{area or sido} 소식", (sido, area))
                    parts.append(r)
                    warns += w
                reply, extra, w = "\n\n---\n\n".join(parts), {"intent": "news", "news": None}, warns
            else:
                scope = regs[-1] if (regs and not req["sido"]) else (session.slots["region"] or None, session.slots["area"])
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
            reply = _issue_message(issues, today)
            if missing:
                reply += "\n\n" + _ask_missing(s)
            stage = "planned" if in_plan else "asking"
        elif missing:
            reply, stage = _ask_missing(s), "asking"
        elif not session.plan and not session.asked_optional and not (s["party"] or s["preferences"]):
            session.asked_optional = True
            reply, stage = _ask_optional(s), "asking"
        else:
            session.asked_optional = True
            reply = _make_plan(session, text, today, ranker, refine=in_plan and not changed, warnings=warnings)
            stage = "planned" if session.plan else "asking"

        session.history.append({"role": "assistant", "content": reply})
        return _pack(session, stage, reply, warnings if stage == "asking" else None)
