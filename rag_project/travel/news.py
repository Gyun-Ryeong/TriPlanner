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
SAFETY_ASK_RE = re.compile(r"범죄|사건\s*[·ㆍ/]?\s*사고")  # '뉴스'라는 말이 없어도 사건·사고를 묻는 표현
BROAD_DAYS, FOCUS_DAYS = 14, 90  # 포괄 질문은 최근 2주, 특정 대상은 최근 3개월 기사까지

# 대상 키워드를 뽑을 때 버리는 말
_FILLER = {"요즘", "최근", "관련", "관련된", "대한", "알려줘", "알려줄래", "알려주세요", "알려", "있어", "있나요", "있니", "있을까", "좀",
           "혹시", "해줘", "보여줘", "찾아줘", "뭐", "뭐가", "어때", "어떤", "무슨", "새로운", "최신", "오늘", "이번", "주요", "핵심", "것", "거",
           "알아야", "알아두면", "알아둘", "알아", "좋은", "정보", "사항", "주의", "주의할", "여행", "여행가는", "가는", "가는데", "가려는", "가려고", "가는데요", "갈", "갈때", "갈건데"}

# ── 사건·사고 질문 ("인천 범죄 뉴스") ────────────────────────────────────
# '범죄' 같은 단어 하나만 검색하면 만화·드라마 기사가 섞여 나오므로, 지역 이름 + 사건 현장 단어가 함께 있는 기사만 고른다.
SAFETY_WORDS = {"범죄", "사건사고", "사건", "사고", "치안", "강력범죄", "범죄사건", "안전사고", "교통사고"}
SAFETY_DAYS = 60  # 최근 두 달
SAFETY_MAX = 6
SAFETY_QUERIES = ("경찰 검거", "범죄", "사건사고", "화재", "교통사고", "폭행 절도")
# 실제 사건·사고 기사에 나오는 말 (이 중 하나는 있어야 통과)
_INCIDENT_RE = re.compile(r"경찰|검거|체포|구속|입건|송치|피의자|피해자|용의자|범행|범죄|사망|숨져|숨진|부상|(?<!문)화재(?!단)|불이|소방|실종|폭행|절도|사기|"
                          r"살인|성범죄|마약|음주운전|추락|붕괴|침수|교통사고|안전사고|강도|납치|보이스피싱|변사|응급|추돌|충돌|전복|심정지|참변|피습|흉기|스토킹|학대")
# 예방 캠페인·기부·예산·정치 기사처럼 사건이 아닌데 단어만 겹치는 제목
_NOT_INCIDENT_RE = re.compile(r"협약|캠페인|훈련|예산|정책|기부|전달받|전달식|공모|박람회|축제|세미나|업무보고|후보자|국정감사|의혹|논란|"
                              r"포상|표창|영웅|수여|유공|예방|대책|접견|청장|임명|취임|출범|개청|감소|증가|행사|기념|체험|수렴|약속|개선|브리핑|메디톡|칼럼|기고|주의|교육|24시|실시")
# 이야기·방송 속 사건이라 여행과 무관한 기사에 나오는 말 (하나라도 있으면 제외)
_FICTION_RE = re.compile(r"드라마|영화|웹툰|애니|코난|예능|배우|소설|게임|개봉|시즌|캐릭터|넷플릭스|뮤지컬|콘서트|아이돌|만화|OTT|시청률|"
                         r"주연|출연|방영|촬영|스포일러|리뷰|줄거리|웹소설|유튜버|가수")
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
    # 대상이 '범죄·사건사고' 같은 말뿐이면 특정 장소 질문이 아니라 사건·사고 질문
    safety = bool(alts) and all(re.sub(r"[\W_]+", "", w) in SAFETY_WORDS for w in alts)
    return {"sido": sido, "area": area, "target": alt, "safety": safety,
            "candidates": list(dict.fromkeys(x for x in (raw_joined, alt) if x))}


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


def _similar(a: str, b: str, threshold: float = 0.5) -> bool:
    x, y = _bigrams(a), _bigrams(b)
    return bool(x and y) and len(x & y) / len(x | y) >= threshold


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


def _incident_kind(title: str) -> str:
    if re.search(r"(?<!문)화재(?!단)|불이|소방|폭발", title):
        return "fire"
    if re.search(r"교통사고|추돌|충돌|전복|음주운전", title):
        return "traffic"
    return "crime"


def pick_safety(items: list[dict], label: str, n: int = SAFETY_MAX, now: datetime | None = None) -> list[dict]:
    """사건·사고: 최근 두 달 기사 중 지역 이름이 있고, 실제 사건 현장 단어가 있으며, 드라마·영화 같은 기사가 아닌 것. 같은 사건은 하나로."""
    key = _norm(label)
    rel = []
    for it in _recent(items, SAFETY_DAYS, now):
        text = it["title"] + " " + it["description"]
        # 지역 이름과 사건 단어가 모두 제목에 있어야 한다 (본문 한 줄에 '범죄 피해자 지원'처럼 스치는 기사 제외)
        if (key in _norm(it["title"]) and _INCIDENT_RE.search(it["title"]) and not _NOT_INCIDENT_RE.search(it["title"])
                and not _FICTION_RE.search(text)):
            rel.append(it)
    rel.sort(key=lambda it: (key in _norm(it["title"]), _when(it)), reverse=True)  # 제목에 지역이 있는 것 → 최신 순
    # 같은 사건을 여러 언론이 쓴 건 하나로 묶고, 화재만 줄줄이 나오지 않게 종류(범죄·화재·교통)마다 2건까지 먼저 담는다
    unique: list[dict] = []
    for it in rel:
        if not any(_similar(it["title"], c["title"], 0.3) for c in unique):
            unique.append(it)
    chosen: list[dict] = []
    per_kind: dict[str, int] = {}
    for it in unique:
        k = _incident_kind(it["title"])
        if per_kind.get(k, 0) < 2 and len(chosen) < n:
            per_kind[k] = per_kind.get(k, 0) + 1
            chosen.append(it)
    for it in unique:  # 자리가 남으면 나머지로 채움
        if len(chosen) >= n:
            break
        if it not in chosen:
            chosen.append(it)
    chosen.sort(key=_when, reverse=True)
    return chosen


def render_safety(label: str, items: list[dict]) -> tuple[str, list[dict]]:
    if not items:
        return f"최근 두 달 안에 {label}에서 알아둘 만한 사건·사고 기사는 찾지 못했어요.", []
    lines = [f"## {label} 최근 사건·사고 소식", "", "최근 두 달 기사 중 해당 지역의 사건·사고만 골랐어요. 최신순입니다.", ""]
    for i, it in enumerate(items, 1):
        lines += [f"**{i}. {it['title']}** ({_date(it)})", f"- {_snippet(it['description'], 110)}", f"- [기사 보기]({it['link']})", ""]
    return "\n".join(lines).strip(), [_view(it) for it in items]


def answer_safety(label: str) -> tuple[str, dict, list[str], bool]:
    items, warnings = fetch([f"{label} {q}" for q in SAFETY_QUERIES], display=50)
    if not items and warnings:
        return NEWS_UNAVAILABLE, {"intent": "news", "news": []}, warnings, False
    reply, views = render_safety(label, pick_safety(items, label))
    return reply, {"intent": "news", "news": views}, warnings, False


NEWS_UNAVAILABLE = "지금은 소식을 불러오지 못했어요. 잠시 뒤에 다시 물어봐 주세요."


def answer_news(text: str, session_scope: tuple[str | None, str]) -> tuple[str, dict, list[str], bool]:
    """
    Returns: (답변, 추가 결과 필드, 개발자 정보용 경고, 지역을 되물어야 하는지)
    session_scope: 이전 대화의 (시도, 세부지역). 질문에 지역이 없을 때 포괄 질문에만 사용.
    """
    req = parse_news_request(text)
    if req["safety"]:  # 사건·사고 질문 (지역 필수, 질문에 없으면 이전 대화의 지역)
        sido, area = (req["sido"], req["area"]) if req["sido"] else session_scope
        label = area or sido
        if not label:
            return "어느 지역의 사건·사고 소식을 알려드릴까요? (예: 인천, 부산, 제주)", {"intent": "news", "news": []}, [], True
        return answer_safety(label)
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
