"""
특정 장소/음식점 정보 문의.  예) "OO식당 정보 알려줘", "XX공원 어떤 곳이야?", "모란시장 영업시간"

추천 요청이 아니므로 다른 곳을 추천하지 않고, 물어본 '그 장소' 하나에 대해서만
📍 도로명 주소 · 🕒 영업/관람 정보 · 💡 주요 특징을 답합니다. (모두 TourAPI 데이터, AI는 쓰지 않음)
"""
import re

from collectors.tourism import get_intro, get_overview, menu_text, operating_text, search_places
from travel.geo import district_of
from travel.ldong import resolve_ldong, resolve_sigungu
from travel.lists import one_liner
from travel.news import _FILLER, _norm, _region_of, variants

# 장소 '정보'를 묻는 표현
INFO_RE = re.compile(r"정보|어떤\s*곳|어떤곳|어떤\s*데|어디야|어디에\s*있|뭐야|뭐하는|소개|영업\s*시간|운영\s*시간|오픈|주소|위치|휴무|쉬는\s*날|몇\s*시|언제\s*열|어때|궁금|상세|자세히")
_REMOVE = re.compile(r"(어떤\s*곳\s*(이야|인가요|이에요|입니까)?|어떤\s*데\s*야?|어디에\s*있\w*|어디\s*야|뭐\s*야|뭐하는\s*곳\w*|소개\s*해?\s*줘|소개|"
                     r"영업\s*시간|운영\s*시간|정보|주소|위치|휴무일?|쉬는\s*날|몇\s*시\w*|언제\s*열\w*|알려\s*줘|알려\s*줄래|알려\s*주세요|"
                     r"가르쳐\s*줘|궁금\w*|자세히|상세|좀|어때\w*|이야|인가요|있어\w*|오픈\w*)")
# 이름이 아닌 일반 명사 (이것만 남으면 특정 장소가 아니라 목록 요청)
GENERIC = {"맛집", "카페", "식당", "음식점", "여행지", "관광지", "명소", "볼거리", "놀거리", "장소", "곳", "데이트", "코스", "일정",
           "근처", "주변", "주위", "추천", "핫플", "먹거리", "디저트", "커피", "베이커리", "여행", "어디", "여기", "거기", "이곳", "그곳"}

NOT_FOUND = "'{name}'에 대한 정보를 찾지 못했어요. 정확한 이름을 다시 알려주시겠어요?"


def parse_place_request(text: str) -> dict:
    """Returns {"sido","area","name","candidates"}. name이 비어 있으면 특정 장소를 지목한 게 아니다."""
    t = _REMOVE.sub(" ", re.sub(r"[?!.,~]", " ", text))
    sido, area, raws, alts = None, "", [], []
    for raw in t.split():
        p, a = variants(raw)
        reg = _region_of(raw) or _region_of(p) or _region_of(a)
        if reg:
            sido, area = reg[0], reg[1] or area
            continue
        if len(a) >= 2 and not ({raw, p, a} & (GENERIC | _FILLER)):
            raws.append(p)
            alts.append(a)
    alt, raw_joined = " ".join(alts), " ".join(raws)
    return {"sido": sido, "area": area, "name": alt, "candidates": list(dict.fromkeys(x for x in (raw_joined, alt) if x))}


def is_place_info_request(text: str) -> bool:
    """장소 정보를 묻는 말이고 특정 이름이 들어 있으며, 추천을 요구하는 말이 아닐 때."""
    if "추천" in text or not INFO_RE.search(text):
        return False
    return bool(parse_place_request(text)["name"])


# ── 검색 ──────────────────────────────────────────────────────────────
def pick_match(places: list[dict], name: str, sido: str | None = None, area: str = "") -> dict | None:
    """검색 결과 중 이름이 가장 정확히 맞는 하나. 이름이 제목에 들어 있지 않으면 None (다른 곳을 억지로 고르지 않는다)."""
    key = _norm(name)
    scored = []
    for p in places:
        title = _norm(p["title"])
        if title == key:
            score = 3
        elif title.startswith(key):
            score = 2
        elif key in title:
            score = 1
        else:
            continue
        place_bonus = (1 if area and area in p["addr"] else 0) + (1 if sido and sido[:2] in p["addr"] else 0)
        scored.append((score, place_bonus, -len(title), p))
    return max(scored, key=lambda x: x[:3])[3] if scored else None


def find_place(candidates: list[str], sido: str | None, area: str) -> tuple[dict | None, list[str]]:
    """이름 후보를 차례로, 지역을 말했으면 그 지역 안에서 먼저 찾고 없으면 전국에서 찾는다."""
    warnings: list[str] = []
    regn, signgu = "", ""
    if sido:
        try:
            regn = resolve_ldong(sido)[0]
            sg = resolve_sigungu(sido, area)
            signgu = sg[0][1] if sg and len(sg) == 1 else ""
        except Exception:
            pass
    for name in candidates:
        scopes = [(regn, signgu), (regn, "")] if regn else []
        scopes.append(("", ""))
        for r, sg_ in dict.fromkeys(scopes):
            try:
                found = pick_match(search_places(name, r, sg_), name, sido, area)
            except Exception as e:
                warnings.append(f"장소 검색 실패('{name}'): {type(e).__name__}: {str(e)[:100]}")
                continue
            if found:
                return found, warnings
    return None, warnings


# ── 표시 ──────────────────────────────────────────────────────────────
def render_place(p: dict, overview: str, intro: dict) -> tuple[str, dict]:
    ctype = str(p.get("content_type_id", ""))
    ops = operating_text(intro, ctype)
    if ctype == "15" and p.get("event_start"):
        period = f"{p['event_start']}~{p.get('event_end') or p['event_start']}"
        ops = f"행사 기간 {period}" + (f" · {ops}" if ops else "")
    menu = menu_text(intro) if ctype == "39" else ""
    feature_parts = [f"대표 메뉴 {menu}" if intro.get("firstmenu") else f"취급 메뉴 {menu}" if menu else "",
                     one_liner(overview, 140)]
    feature = " · ".join(x for x in feature_parts if x) or f"{district_of(p['addr']) or ''}에 있는 {p['content_type']}이에요.".strip()
    lines = [f"## {p['title']}"]
    if p["addr"]:
        lines.append(f"- 📍 도로명 주소: {p['addr']}")
    lines.append(f"- 🕒 영업/관람 정보: {ops or '정확한 운영 시간은 방문 전에 확인해 주세요.'}")
    lines.append(f"- 💡 주요 특징: {feature}")
    view = {"name": p["title"], "type": p["content_type"], "address": p["addr"], "operating": ops, "feature": feature,
            "image": p.get("image", ""), "mapx": p.get("mapx", ""), "mapy": p.get("mapy", ""), "content_id": p.get("content_id", "")}
    return "\n".join(lines), view


def answer_place(text: str) -> tuple[str, dict, list[str]]:
    """Returns (답변, 추가 결과 필드, 개발자 정보용 경고). 찾지 못해도 다른 곳을 추천하지 않는다."""
    req = parse_place_request(text)
    place, warnings = find_place(req["candidates"], req["sido"], req["area"])
    if place is None:
        return NOT_FOUND.format(name=req["name"]), {"intent": "place_info", "place": None}, warnings
    overview, intro = "", {}
    try:
        overview = get_overview(place["content_id"])
    except Exception as e:
        warnings.append(f"소개글 조회 실패: {type(e).__name__}: {str(e)[:100]}")
    try:
        intro = get_intro(place["content_id"], place["content_type_id"])
    except Exception as e:
        warnings.append(f"운영 정보 조회 실패: {type(e).__name__}: {str(e)[:100]}")
    reply, view = render_place(place, overview, intro)
    return reply, {"intent": "place_info", "place": view}, warnings
