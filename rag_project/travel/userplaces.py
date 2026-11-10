"""
사용자가 직접 말한 장소: 숙소, 꼭 들를 카페·식당·명소(시간은 있어도 되고 없어도 됨).

  "숙소는 판교 스타호텔이야, 2일차 12시에 단풍 카페 들를게, 저녁 7시에 OO식당 예약했어"
   → 숙소 1곳(하루의 출발·복귀 지점) + 방문 장소 2곳(시간이 있으면 그 시각에 고정)

말을 규칙으로 읽고(AI 없이), 위치는 TourAPI 후보에서 먼저 찾고 없으면 네이버 지역검색으로 찾는다.
이 파일은 외부 상태 없이 입력 → 출력만 다룬다 (세션 연결은 chat.py).
"""
import hashlib
import re

from travel.clock import parse_time_range, strip_times
from travel.geo import straight_km
from travel.news import _REGION_TOKENS
from travel.places import is_indoor

LODGING_RE = re.compile(r"숙소|숙박|묵을|묵는|묵어|묵고|묵을래|체크\s*인|체크\s*아웃|(?:호텔|펜션|리조트|모텔|게스트하우스)\s*예약|예약\s*(?:한|해둔|해 둔)?\s*(?:호텔|펜션|리조트|모텔)")
STRONG_RE = re.compile(r"들르|들러|들릴|들를|들렀|예약|넣어|넣고|넣을|포함|추가|꼭|무조건|반드시|묵")
WEAK_RE = re.compile(r"가고|가려|갈래|갈게|갈거|갈\s*것|갈건|가는|먹을|먹고|마실|마시")
DROP_RE = re.compile(r"빼|제외|취소|삭제|없애|지워")
MOVE_RE = re.compile(r"옮겨|옮기|이동해|미뤄|당겨|바꿔")  # "하늘식당 2일차로 옮겨줘" (일차를 같이 말했을 때만)

_DAY_REF_RE = re.compile(r"(\d{1,2})\s*일\s*차|(\d{1,2})\s*번?\s*째\s*날|(첫|둘|셋|넷|다섯|여섯|일곱|여덟|아홉|열)\s*(?:째)?\s*날|(마지막|끝)\s*날")
_ORDINAL = {"첫": 1, "둘": 2, "셋": 3, "넷": 4, "다섯": 5, "여섯": 6, "일곱": 7, "여덟": 8, "아홉": 9, "열": 10}
_SPLIT_RE = re.compile(r"[,，;\n]|\s그리고\s|\s및\s|\s(?:근데|그런데|하지만|그래서|참고로)\s|(?<=[.!?。])\s*|(?<=이고)\s+|(?<=이며)\s+|(?<=인데)\s+|(?<=이지만)\s+")
_QUOTED_RE = re.compile(r"[\"'“‘「『]([^\"'“”‘’」』]{2,30})[\"'”’」』]")  # 따옴표로 묶은 이름 ("'신라모노그램 강릉'")
NO_LODGING_RE = re.compile(r"숙소\s*(?:는|은)?\s*(?:없이|없어|없는|안\s*정했|아직|상관\s*없|필요\s*없)|숙소\s*없이|그냥\s*(?:짜|진행)|일단\s*(?:짜|진행)")
_NUM_PREFIX_RE = re.compile(r"^\s*(?:\d+[.)]|[-•·*])\s+")
_DATE_RE = re.compile(r"\d{1,2}\s*월\s*\d{1,2}\s*일|\d{1,2}\s*월|\d+\s*박\s*\d*\s*일?|\d+\s*일")

_PARTICLE_MULTI_RE = re.compile(r"(에서는|에서|에는|으로|이랑|하고|이고|이며|인데|입니다|이에요|예요|이야|쯤으로|쯤)$")
_PARTICLE_ONE_RE = re.compile(r"(에|은|는|이|가|을|를|도|만|의|과|와|랑|로)$")
_DROP_WORDS = {"숙소", "숙박", "체크인", "체크아웃", "예약", "꼭", "무조건", "반드시", "먼저", "그리고", "및", "여기", "거기", "저기", "거", "것", "곳",
               "장소", "일정", "여행", "좀", "한번", "한", "번", "근처", "주변", "앞", "옆", "쪽", "아침", "점심", "저녁", "오전", "오후", "낮", "새벽", "밤",
               "브런치", "조식", "석식", "중식", "내일", "모레", "오늘", "이번", "다음", "주말", "그날", "그", "저", "이", "우리", "나", "제가", "저는",
               "예정", "근데", "그런데", "하지만", "그래서", "이미", "기반", "동선", "효율적인", "효율적", "좋겠어", "좋겠어요", "원해", "부탁"}
_DROP_STEMS = ("들르", "들러", "들릴", "들를", "들렀", "가고", "가려", "갈래", "갈게", "갈거", "갈것", "갈건", "가는", "갔", "예약", "잡았", "잡아",
               "묵을", "묵어", "묵고", "묵는", "넣어", "넣고", "넣을", "추가", "포함", "먹을", "먹고", "먹으", "마실", "마시", "출발", "도착", "시작",
               "끝나", "빼", "제외", "취소", "삭제", "없애", "지워", "바꿔", "변경", "옮겨", "해줘", "해주", "알려", "짜줘", "짜주", "짜줬", "짜줄", "싶", "하고싶", "좋겠", "원하", "부탁", "효율", "예정")
_VERBISH_END = ("요", "죠", "까", "네", "니다", "해", "줘", "려고", "려는", "서", "게", "래", "다", "데")
GENERIC_NAMES = {"맛집", "식당", "카페", "커피", "디저트", "술집", "박물관", "미술관", "공원", "해변", "바다", "시장", "관광지", "명소", "실내", "야외",
                 "코스", "축제", "행사", "공연", "체험", "쇼핑", "호텔", "펜션", "리조트", "음식점", "밥집", "빵집", "산", "계곡", "전시"}


def _norm(s: str) -> str:
    return re.sub(r"[\W_]+", "", s or "")


def _day_ref(seg: str) -> int | None:
    """말한 일차(1부터, 마지막 날은 -1). 없으면 None."""
    m = _DAY_REF_RE.search(seg)
    if not m:
        return None
    if m.group(1) or m.group(2):
        return int(m.group(1) or m.group(2))
    return _ORDINAL[m.group(3)] if m.group(3) else -1


def _name_tokens(seg: str) -> list[tuple[str, str]]:
    """
    한 구절에서 시간·날짜·일차·동사·조사를 걷어내고 장소 이름 조각만 남긴다.
    Returns: [(비교용 조각, 검색용 조각)] — 검색용은 한 글자 조사를 떼지 않은 형태 ('스카이베이'를 '스카이베'로 자르지 않는다)
    """
    s = strip_times(seg)
    s = _DAY_REF_RE.sub(" ", s)
    s = _DATE_RE.sub(" ", s)
    s = re.sub(r"[()\[\]\"'“”‘’~!?.:]", " ", s)
    out = []
    for raw in s.split():
        search = _PARTICLE_MULTI_RE.sub("", raw)
        search = search if len(search) >= 2 else raw
        t = _PARTICLE_ONE_RE.sub("", search)
        t = t if len(t) >= 2 else search
        if len(t) < 2 or t in _DROP_WORDS or t.startswith(_DROP_STEMS) or raw.startswith(_DROP_STEMS):
            continue
        if t.endswith("요일") or t in ("다음주", "이번주", "담주", "평일", "휴일", "공휴일", "연휴", "당일", "첫날", "마지막날", "하루"):
            continue
        if t.endswith(_VERBISH_END) and len(t) <= 4:
            continue
        out.append((t, search))
    return out


def _is_region(tok: str) -> bool:
    return tok in _REGION_TOKENS or (len(tok) > 2 and tok.endswith(("시", "군", "구", "도")) and tok[:-1] in _REGION_TOKENS)


def parse_directives(text: str, is_known_other=lambda seg: False) -> dict:
    """
    Returns: {"items": [{"kind": "stay"|"visit"|"drop", "name", "tokens", "time", "day", "strong"}], "rest": 처리하지 않은 말, "only": 장소 말만 있는가}
    is_known_other(구절): 이미 일정에 있는 축제처럼 다른 기능이 맡는 구절이면 True (건너뜀)
    """
    t = re.sub(r"(들르고|들리고|들렀다가|먹고|묵고)\s+", r"\1, ", text or "")
    items, rest = [], []
    for seg in (x.strip() for x in _SPLIT_RE.split(t)):
        seg = _NUM_PREFIX_RE.sub("", seg).strip()
        if len(seg) < 2:
            continue
        if is_known_other(seg):
            rest.append(seg)
            continue
        stay = bool(LODGING_RE.search(seg))
        drop = bool(DROP_RE.search(seg)) and not stay
        strong, weak = bool(STRONG_RE.search(seg)), bool(WEAK_RE.search(seg))
        tm = parse_time_range(seg)
        day = _day_ref(seg)
        move = day is not None and bool(MOVE_RE.search(seg)) and not (stay or drop or strong or tm)
        if not (stay or drop or strong or weak or tm or move):
            rest.append(seg)
            continue
        quoted = _QUOTED_RE.search(seg)
        all_tokens = _name_tokens(quoted.group(1) if quoted else seg)  # 따옴표로 묶은 이름이 있으면 그것만이 장소 이름
        tokens = [x for x, _ in all_tokens if not _is_region(x) and _norm(x) not in GENERIC_NAMES]
        search_tokens = [r for x, r in all_tokens if not _is_region(x) and _norm(x) not in GENERIC_NAMES]
        generic = [x for x, _ in all_tokens if _norm(x) in GENERIC_NAMES]
        strong_signal = stay or drop or strong or tm is not None or move
        # "광안리 횟집 가고 싶어"처럼 종류만 말한 짧은 이름은 특정 장소가 아니다 (시간·'꼭' 같은 분명한 말이 있을 때만 장소로 본다)
        if not tokens or (not strong_signal and len(_norm("".join(tokens))) < 4):
            rest.append(seg)
            continue
        items.append({"kind": "stay" if stay else "drop" if drop else "move" if move else "visit", "name": " ".join(tokens), "tokens": tokens,
                      "search_tokens": search_tokens, "region_tokens": [x for x, _ in all_tokens if _is_region(x)], "generic": generic, "display": quoted.group(1).strip() if quoted else " ".join(tokens),
                      "time": None if drop else tm, "day": day, "strong": stay or strong or tm is not None})
    rest_text = " ".join(rest).strip()
    return {"items": items, "rest": rest_text, "only": bool(items) and len(_norm(rest_text)) < 2}


def lodging_item_from_reply(text: str) -> dict | None:
    """숙소 위치를 못 찾아 되물은 뒤의 답("신라모노그램 강릉 경포")을 숙소 이름으로 읽는다. 숙소라는 말이 없어도 된다."""
    quoted = _QUOTED_RE.search(text)
    all_tokens = _name_tokens(quoted.group(1) if quoted else text)
    tokens = [x for x, _ in all_tokens if not _is_region(x) and _norm(x) not in GENERIC_NAMES]
    if not tokens or len(_norm(text)) > 60:
        return None
    return {"kind": "stay", "name": " ".join(tokens), "tokens": tokens,
            "search_tokens": [r for x, r in all_tokens if not _is_region(x) and _norm(x) not in GENERIC_NAMES],
            "region_tokens": [x for x, _ in all_tokens if _is_region(x)],
            "generic": [x for x, _ in all_tokens if _norm(x) in GENERIC_NAMES], "time": None, "day": None, "strong": True,
            "display": quoted.group(1).strip() if quoted else " ".join(tokens)}


# ── 위치 찾기 ─────────────────────────────────────────────────────────
def _match_score(tokens: list[str], title: str) -> int:
    nt = _norm(title)
    return sum(1 for t in tokens if _norm(t) in nt)


def match_pool(name: str, pool: list[dict]) -> dict | None:
    """이미 가진 관광 후보(TourAPI) 중 이름이 같은 장소. 짧은 이름은 오탐이 많아 3글자 이상만."""
    n = _norm(name)
    if len(n) < 3:
        return None
    for p in pool:
        t = _norm(p.get("title", ""))
        if len(t) >= 3 and (n == t or n in t or t in n):
            return p
    return None


_FOOD_HEADS = {"음식점", "한식", "양식", "일식", "중식", "분식", "간식", "술집", "아시아음식", "패스트푸드", "뷔페", "카페,디저트", "퓨전요리", "해물", "육류"}


def to_place(r: dict, kind: str, display_name: str = "") -> dict:
    """네이버 지역검색 결과 → 일정에 쓰는 장소 형식 (TourAPI 장소와 같은 키)."""
    cat = r.get("category", "")
    head = cat.split(">")[0]
    cafe = "카페" in cat or head in ("간식", "카페,디저트")
    food = head in _FOOD_HEADS or cafe
    lodging = kind == "stay" or head == "숙박"
    ctype, label = ("32", "숙소") if lodging else ("39", "카페" if cafe else "음식점") if food else ("12", "장소")
    title = r["title"]
    if kind == "stay" and head != "숙박" and display_name:
        title = display_name  # 호텔 안의 식당이 검색돼도(위치는 같은 건물) 사용자가 말한 숙소 이름으로 보여준다
    p = {
        "source": "naver_local", "content_id": "naver:" + hashlib.md5(f"{title}|{r['addr']}".encode("utf-8")).hexdigest()[:10],
        "title": title, "addr": r.get("addr", ""), "content_type_id": ctype, "content_type": label,
        "mapx": r.get("mapx", ""), "mapy": r.get("mapy", ""), "image": "", "overview": cat,
        "event_start": "", "event_end": "", "raw": {}, "related_news_ids": [], "user_pick": True,
        "stay_min": 60 if cafe else 70 if food else 90, "meal": bool(food and not cafe and not lodging),
    }
    p["indoor"] = True if cafe or lodging else is_indoor(p)
    return p


def find_place(item: dict, region_hint: str, pool: list[dict], search, addr_ok=None) -> tuple[dict | None, str]:
    """
    말한 이름으로 장소를 찾는다. Returns: (장소 또는 None, 경고)
    search(query) → 네이버 지역검색 결과 목록 (테스트에서 바꿔 끼울 수 있다)
    addr_ok(주소) → 여행 지역 안의 주소인가 (아니면 같은 이름의 다른 지역 가게를 고르지 않도록 걸러낸다)
    """
    if item["kind"] != "stay":
        hit = match_pool(item["name"], pool)
        if hit is not None:
            return dict(hit), ""
    tokens, generic = item["tokens"], item.get("generic", [])
    qtokens = item.get("search_tokens") or tokens  # 검색어에는 한 글자 조사를 떼지 않은 형태
    loc = item.get("region_tokens") or ([region_hint] if region_hint else [])
    hint = [region_hint] if region_hint else []
    queries = list(dict.fromkeys(" ".join(q) for q in (loc[:2] + qtokens + generic, hint + qtokens + generic, qtokens + generic,
                                                       loc[:2] + tokens + generic)))
    # 그래도 안 되면 긴 이름 조각 하나씩 (문장 조각이 섞여 이름이 길어진 경우)
    for tok in sorted(qtokens, key=len, reverse=True)[:3]:
        if len(_norm(tok)) >= 3:
            queries.append(" ".join(loc[:1] + [tok] + generic[:1]))
    queries = list(dict.fromkeys(queries))
    best, best_score, warn = None, 0.0, ""
    for q in queries:
        try:
            results = search(q)
        except Exception as e:
            warn = f"장소 검색 실패('{q}'): {type(e).__name__}: {str(e)[:100]}"
            continue
        for r in results:
            sc = _match_score(tokens, r["title"])
            if not (sc > 0 and (len(tokens) < 2 or sc * 2 >= len(tokens)) and r.get("mapx")):
                continue
            if addr_ok is not None and not addr_ok(r.get("addr", "")):
                continue
            if item["kind"] == "stay" and r.get("category", "").startswith("숙박"):
                sc += 0.5  # 숙소를 말했으면 숙박 시설을 우선
            if sc > best_score:
                best, best_score = r, sc
        if best is not None:
            break
    if best is None:
        return None, warn
    place = to_place(best, item["kind"], item.get("display") or " ".join(tokens + generic))
    place["approx"] = best_score < len(tokens)  # 말한 이름 조각 중 일부만 맞은 경우: 사용자에게 확인을 부탁한다
    return place, warn


# ── 일정에 넣기 ───────────────────────────────────────────────────────
def key_of(p: dict) -> str:
    return p.get("content_id") or p.get("title")


def _nearest_day(place: dict, days: list[dict], cand_map: dict, load: dict[int, int]) -> int:
    """아직 하루가 정해지지 않은 장소: 그 장소와 가장 가까운 장소가 있는 날 (이미 사용자 장소가 몰린 날은 조금 불리하게)."""
    best, best_d = 0, 1e9
    for i, day in enumerate(days):
        ds = [d for d in (straight_km(place, cand_map[it["candidate_id"]]) for it in day["items"] if it["candidate_id"] in cand_map)
              if d is not None]
        score = (min(ds) if ds else 5.0) + 2.0 * load.get(i, 0) + 0.3 * len(day["items"])
        if score < best_d:
            best, best_d = i, score
    return best


def integrate(entries: list[dict], days: list[dict], cand_map: dict, cid_of, max_items: int = 6) -> dict[int, list[str]]:
    """
    사용자가 고른 장소를 일정에 넣는다 (이미 있으면 빼고 다시 넣는다 — 몇 번을 불러도 같은 결과).
    entries: [{"place", "day"(0부터 또는 None), ...}]. 각 entry 에 "assigned_day" 를 기록한다.
    Returns: {일차: [후보 id, ...]}
    """
    cids = {}
    for e in entries:
        cid = cid_of(e["place"])
        cand_map[cid] = e["place"]
        cids[key_of(e["place"])] = cid
    mine = set(cids.values())
    for d in days:
        d["items"] = [it for it in d["items"] if it["candidate_id"] not in mine]
    placed: dict[int, list[str]] = {}
    load: dict[int, int] = {}
    for e in sorted(entries, key=lambda e: (e.get("day") is None, e["time"] is None if e.get("time") else True)):
        di = e["day"] if e.get("day") is not None and 0 <= e["day"] < len(days) else _nearest_day(e["place"], days, cand_map, load)
        cid = cids[key_of(e["place"])]
        days[di]["items"].append({"slot": "", "candidate_id": cid, "note": "직접 고르신 장소예요."})
        placed.setdefault(di, []).append(cid)
        load[di] = load.get(di, 0) + 1
        e["assigned_day"] = di
    for di, d in enumerate(days):  # 하루 최대치를 넘으면 사용자가 고르지 않은 뒤쪽 장소부터 뺀다
        while sum(1 for it in d["items"] if it["candidate_id"]) > max_items:
            j = next((j for j in range(len(d["items"]) - 1, -1, -1) if d["items"][j]["candidate_id"] not in mine), None)
            if j is None:
                break
            d["items"].pop(j)
    return placed
