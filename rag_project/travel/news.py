"""
지역 뉴스 질문 대응.

  Case A 포괄 질문  "성남시 요즘 소식 있어?"        → 그 지역 핵심 소식 3~4개 (같은 사건을 여러 언론이 쓴 건 하나로)
  Case B 특정 대상  "성남 야외공연장 뉴스 알려줘"    → 그 대상과 직접 관련된 뉴스 '하나'만 (무관한 기사는 제외)

네이버 뉴스 검색 결과(제목·요약)만 사용하고 AI는 쓰지 않습니다. 기사에 없는 내용을 지어낼 수 없고 빠릅니다.
"""
import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

from collectors.naver_news import search_news
from travel.regions import CITY_TO_SIDO, SIDO, normalize_region

NEWS_RE = re.compile(r"뉴스|소식|이슈|기사|근황|동향")
BROAD_DAYS, FOCUS_DAYS = 14, 90  # 포괄 질문은 최근 2주, 특정 대상은 최근 3개월 기사까지

# 대상 키워드를 뽑을 때 버리는 말
_FILLER = {"요즘", "최근", "관련", "관련된", "대한", "알려줘", "알려줄래", "알려주세요", "알려", "있어", "있나요", "있니", "있을까", "좀",
           "혹시", "해줘", "보여줘", "찾아줘", "뭐", "뭐가", "어때", "어떤", "무슨", "새로운", "최신", "오늘", "이번", "주요", "핵심", "것", "거"}
_PARTICLE_MULTI = re.compile(r"(에서|에게|으로|에는|이라는|이란|에대한|이라고|이랑|하고|까지|부터)$")
_PARTICLE_ONE = re.compile(r"(은|는|이|가|을|를|과|와|도|만|로|의|에|랑)$")
_NAME_ENDINGS = ("마을", "산책로", "등산로", "순환로", "해안로", "대로")  # 조사처럼 보이는 글자로 끝나지만 이름의 일부인 경우

_REGION_TOKENS = set(SIDO) | {a for v in SIDO.values() for a in v["aliases"]} | set(CITY_TO_SIDO)


def variants(w: str) -> tuple[str, str]:
    """(조사를 일부만 제거한 원형, 한 글자 조사까지 제거한 형태). '산책로'처럼 조사 같은 글자로 끝나는 이름이 있어 둘 다 시도한다."""
    p = _PARTICLE_MULTI.sub("", w)
    p = p if len(p) >= 2 else w
    if p.endswith(_NAME_ENDINGS):
        return p, p
    a = _PARTICLE_ONE.sub("", p)
    return p, (a if len(a) >= 2 and len(p) >= 3 else p)


def _region_of(token: str) -> tuple[str, str] | None:
    """토큰이 지역 이름이면 (시도, 세부지역). '성남시' → ('경기','성남'). 단어 속 글자(서울대병원)는 지역으로 보지 않는다."""
    for w in {token, token[:-1] if len(token) > 2 and token.endswith(("시", "군", "구", "도")) else token}:
        if w in CITY_TO_SIDO:
            return CITY_TO_SIDO[w], w
        sido = normalize_region(w) if w in _REGION_TOKENS else None
        if sido:
            return sido, ""
    return None


def parse_news_request(text: str) -> dict:
    """
    Returns: {"sido": 시도|None, "area": 세부지역, "target": 대상 키워드(없으면 ""), "candidates": [원형, 조사 제거형]}
    대상 키워드가 없으면 포괄 질문(Case A), 있으면 특정 대상 질문(Case B).
    """
    t = NEWS_RE.sub(" ", re.sub(r"[?!.,~]", " ", text))
    t = re.sub(r"(알려\s*줘|알려\s*줄래|알려\s*주세요|보여\s*줘|찾아\s*줘|해\s*줘|있\s*(어|나요|니|을까|는지)|"
               r"어떻게\s*(됐|되)\w*|무슨\s*일|어떤\s*일|싶\w*|궁금\w*)", " ", t)
    sido, area, raws, alts = None, "", [], []
    for raw in t.split():
        p, a = variants(raw)
        reg = _region_of(raw) or _region_of(p) or _region_of(a)
        if reg:
            sido, area = reg[0], reg[1] or area
            continue
        if len(a) >= 2 and not ({raw, p, a} & _FILLER):
            raws.append(p)
            alts.append(a)
    alt, raw_joined = " ".join(alts), " ".join(raws)
    return {"sido": sido, "area": area, "target": alt, "candidates": list(dict.fromkeys(x for x in (raw_joined, alt) if x))}


# ── 검색·필터 ─────────────────────────────────────────────────────────
def _norm(s: str) -> str:
    return re.sub(r"[\s\W_]+", "", s or "")


def _when(item: dict) -> datetime | None:
    try:
        d = parsedate_to_datetime(item.get("pub_date", ""))
    except Exception:
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _bigrams(s: str) -> set[str]:
    s = _norm(s)
    return {s[i:i + 2] for i in range(len(s) - 1)}


def _similar(a: str, b: str) -> bool:
    x, y = _bigrams(a), _bigrams(b)
    return bool(x and y) and len(x & y) / len(x | y) >= 0.5


def fetch(queries: list[str], display: int = 20) -> tuple[list[dict], list[str]]:
    """여러 검색어로 모아서 링크·제목 중복을 제거. 실패한 검색어는 건너뛰고 사유를 경고로 돌려준다."""
    items, warnings, seen = [], [], set()
    for q in dict.fromkeys(q for q in queries if q):
        try:
            got = search_news(q, display=display, sort="date")
        except Exception as e:
            warnings.append(f"뉴스 검색 실패('{q}'): {type(e).__name__}: {str(e)[:100]}")
            continue
        for it in got:
            key = it.get("link") or _norm(it["title"])
            if key not in seen:
                seen.add(key)
                items.append(it)
    return items, warnings


def _recent(items: list[dict], days: int, now: datetime | None = None) -> list[dict]:
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=days)
    return [it for it in items if (d := _when(it)) is not None and d >= cutoff]


def pick_broad(items: list[dict], label: str, n: int = 4, now: datetime | None = None) -> list[dict]:
    """포괄 질문: 지역 이름이 제목/요약에 있는 최근 기사 중 같은 사건은 하나로 묶어 핵심 3~4개."""
    key = _norm(label)
    rel = [it for it in _recent(items, BROAD_DAYS, now) if key in _norm(it["title"] + it["description"])]
    rel.sort(key=lambda it: (key in _norm(it["title"]), _when(it)), reverse=True)  # 제목에 지역이 있는 것 → 최신 순
    chosen: list[dict] = []
    for it in rel:
        if not any(_similar(it["title"], c["title"]) for c in chosen):
            chosen.append(it)
        if len(chosen) >= n:
            break
    return chosen


def pick_focus(items: list[dict], target: str, scope: str = "", now: datetime | None = None) -> dict | None:
    """특정 대상: 대상 키워드가 모두 들어 있는(띄어쓰기 무시) 기사 중 하나. 지역을 말했으면 그 지역도 있어야 한다."""
    toks = [_norm(w) for w in target.split() if _norm(w)]
    scope_key = _norm(scope)
    cands = []
    for it in _recent(items, FOCUS_DAYS, now):
        title, body = _norm(it["title"]), _norm(it["title"] + it["description"])
        if all(t in body for t in toks) and (not scope_key or scope_key in body):
            cands.append((all(t in title for t in toks), _when(it), it))
    if not cands:
        return None
    cands.sort(key=lambda c: (c[0], c[1]), reverse=True)  # 제목에 대상이 있는 기사 → 최신
    return cands[0][2]


# ── 표시 ──────────────────────────────────────────────────────────────
def _snippet(text: str, limit: int) -> str:
    t = re.sub(r"\s+", " ", text or "").strip()
    return t if len(t) <= limit else t[:limit].rstrip() + "…"


def _date(item: dict) -> str:
    d = _when(item)
    return d.astimezone().strftime("%m/%d") if d else ""


def _view(it: dict) -> dict:
    return {"title": it["title"], "summary": _snippet(it["description"], 160), "link": it["link"], "pub_date": it.get("pub_date", "")}


def render_broad(label: str, items: list[dict]) -> tuple[str, list[dict]]:
    if not items:
        return f"최근 {label} 관련 소식을 찾지 못했어요.", []
    lines = [f"## {label} 최근 소식", ""]
    for i, it in enumerate(items, 1):
        lines += [f"**{i}. {it['title']}** ({_date(it)})", f"- {_snippet(it['description'], 110)}", f"- [기사 보기]({it['link']})", ""]
    return "\n".join(lines).strip(), [_view(it) for it in items]


def _wa(word: str) -> str:
    """받침이 있으면 '과', 없으면 '와'."""
    ch = word.strip()[-1:] if word.strip() else ""
    return "과" if ch and 0xAC00 <= ord(ch) <= 0xD7A3 and (ord(ch) - 0xAC00) % 28 else "와"


def render_focus(target: str, item: dict | None) -> tuple[str, list[dict]]:
    if item is None:
        return f"'{target}'{_wa(target)} 직접 관련된 최근 소식은 찾지 못했어요.", []
    text = "\n".join([f"## {target} 관련 소식", "", f"**{item['title']}** ({_date(item)})", "",
                      _snippet(item["description"], 220), "", f"[기사 보기]({item['link']})"])
    return text, [_view(item)]


NEWS_UNAVAILABLE = "지금은 소식을 불러오지 못했어요. 잠시 뒤에 다시 물어봐 주세요."


def answer_news(text: str, session_scope: tuple[str | None, str]) -> tuple[str, dict, list[str], bool]:
    """
    Returns: (답변, 추가 결과 필드, 개발자 정보용 경고, 지역을 되물어야 하는지)
    session_scope: 이전 대화의 (시도, 세부지역). 질문에 지역이 없을 때 포괄 질문에만 사용.
    """
    req = parse_news_request(text)
    if req["target"]:  # Case B
        scope = req["area"] or req["sido"] or ""
        items, warnings = fetch([f"{scope} {req['target']}".strip(), req["target"]])
        if not items and warnings:
            return NEWS_UNAVAILABLE, {"intent": "news", "news": []}, warnings, False
        for cand in req["candidates"]:
            found = pick_focus(items, cand, scope)
            if found:
                reply, views = render_focus(req["target"], found)
                return reply, {"intent": "news", "news": views}, warnings, False
        reply, views = render_focus(req["target"], None)
        return reply, {"intent": "news", "news": views}, warnings, False

    sido, area = (req["sido"], req["area"]) if req["sido"] else session_scope  # Case A
    label = area or sido
    if not label:
        return "어느 지역 소식을 알려드릴까요? (예: 성남, 부산, 제주)", {"intent": "news", "news": []}, [], True
    items, warnings = fetch([label, f"{label} 소식", f"{label}시" if not label.endswith(("시", "군", "구")) and area else ""])
    if not items and warnings:
        return NEWS_UNAVAILABLE, {"intent": "news", "news": []}, warnings, False
    reply, views = render_broad(label, pick_broad(items, label))
    return reply, {"intent": "news", "news": views}, warnings, False
