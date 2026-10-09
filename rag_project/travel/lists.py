"""
단발성 추천 답변 (일정 없이 지역만 알면 바로 답한다).

  recommend (Type A) 테마별 여행지 목록        : 장소명 · 📍주소 · 💡특징 1~2줄
  food      (Type C) 맛집/카페 3~5곳           : 📍위치 · 🍴대표 메뉴/특징 · 🚶접근성

장소명·주소·메뉴·영업시간은 모두 TourAPI 데이터이고, 특징 문장은 장소 소개글을 잘라서 씁니다 (AI가 지어내지 않음).
"""
import re

from collectors.tourism import access_text, course_text, lodging_text, menu_text
from travel.geo import district_of
from travel.places import SIGHT_TYPES

CAFE_ASK_RE = re.compile(r"카페|커피|디저트|베이커리|브런치|빵|찻집|케이크")
CAFE_TITLE_RE = re.compile(r"카페|커피|coffee|cafe|베이커리|제과|디저트|브런치|찻집|티룸|로스터|빵집", re.I)
ONLY_SIGHTS_RE = re.compile(r"(여행지|관광지|명소|장소|볼거리)\s*만")  # "여행지만 추천해줘" → 맛집은 빼고
INDOOR_ASK_RE = re.compile(r"실내")
OUTDOOR_ASK_RE = re.compile(r"야외|자연|공원|산책")

SHOP_WORDS = ("백화점", "아울렛", "쇼핑", "시장", "아쿠아리움", "테마파크", "체험관")
WALK_WORDS = ("산책", "둘레길", "올레길", "갈맷길", "자전거길", "등산로", "트레킹", "숲길", "호숫길")
HISTORY_WORDS = ("박물관", "미술관", "기념관", "유적", "사찰", "궁", "성곽", "산성", "향교", "고택", "한옥", "문화원", "역사", "문화재", "서원", "전시")
NATURE_WORDS = ("공원", "호수", "수목원", "정원", "해수욕장", "해변", "계곡", "폭포", "전망대", "숲", "생태", "습지")

CATEGORY_ORDER = ["🌳 자연·공원", "🏛 문화·역사", "🚶 힐링·산책", "🛍 쇼핑·실내", "🏙 도시·명소", "🎡 체험·액티비티", "🎪 축제·행사"]
MAX_PER_CATEGORY, MAX_RECOMMEND = 3, 12


def categorize(place: dict) -> str:
    title, t = place["title"], str(place.get("content_type_id", ""))
    if t == "15":
        return "🎪 축제·행사"
    if t == "28":
        return "🎡 체험·액티비티"
    if t == "38" or any(w in title for w in SHOP_WORDS):
        return "🛍 쇼핑·실내"
    if any(w in title for w in WALK_WORDS):
        return "🚶 힐링·산책"
    if t == "14" or any(w in title for w in HISTORY_WORDS):
        return "🏛 문화·역사"
    if any(w in title for w in NATURE_WORDS):
        return "🌳 자연·공원"
    return "🏙 도시·명소"


def one_liner(text: str, limit: int = 110) -> str:
    """소개글에서 앞쪽 1~2문장을 limit자 안에서 자른다."""
    t = re.sub(r"\s+", " ", text or "").strip()
    if not t:
        return ""
    if len(t) <= limit:
        return t
    cut = t[:limit]
    end = max(cut.rfind("다."), cut.rfind(". "), cut.rfind("요."))
    return (cut[: end + 1] if end >= limit * 0.5 else cut.rstrip() + "…").strip()


def select_recommend(places: list[dict], text: str, rank) -> list[tuple[str, list[dict]]]:
    """여행지 후보를 취향순으로 골라 테마별로 묶는다. rank: 후보 리스트를 유사도 순으로 정렬해주는 함수."""
    pool = [p for p in places if str(p.get("content_type_id")) in SIGHT_TYPES]
    if INDOOR_ASK_RE.search(text):
        pool = [p for p in pool if p.get("indoor")] or pool
    elif OUTDOOR_ASK_RE.search(text):
        pool = [p for p in pool if not p.get("indoor")] or pool
    groups: dict[str, list[dict]] = {}
    total = 0
    for p in rank(pool):
        if total >= MAX_RECOMMEND:
            break
        g = groups.setdefault(categorize(p), [])
        if len(g) < MAX_PER_CATEGORY:
            g.append(p)
            total += 1
    return [(c, groups[c]) for c in CATEGORY_ORDER if groups.get(c)]


def info_score(p: dict) -> int:
    """메뉴·영업 정보가 얼마나 채워져 있는지 (많을수록 좋은 답변이 되므로 우선 선택)."""
    intro = p.get("intro") or {}
    return (2 if intro.get("firstmenu") else 1 if intro.get("treatmenu") else 0) + (1 if access_text(intro) else 0)


FOOD_POOL, FOOD_SHOW = 12, 5  # 소개 정보를 조회할 후보 수 / 보여줄 수


def select_food(places: list[dict], text: str, rank, n: int = FOOD_SHOW) -> list[dict]:
    pool = [p for p in places if str(p.get("content_type_id")) == "39"]
    cafes = [p for p in pool if CAFE_TITLE_RE.search(p["title"])]
    if CAFE_ASK_RE.search(text):
        pool = cafes or pool
    else:
        pool = [p for p in pool if p not in cafes] or pool
    return rank(pool)[:n]


def _view(p: dict, **extra) -> dict:
    return {"name": p["title"], "type": p["content_type"], "address": p["addr"], "indoor": bool(p.get("indoor")),
            "image": p.get("image", ""), "mapx": p.get("mapx", ""), "mapy": p.get("mapy", ""),
            "content_id": p.get("content_id", ""), **extra}


def render_recommend(label: str, groups: list[tuple[str, list[dict]]]) -> tuple[str, list[dict]]:
    lines, views = [f"## {label} 여행지 추천", ""], []
    for cat, items in groups:
        lines.append(f"### {cat}")
        for p in items:
            addr = f" (📍 {p['addr']})" if p["addr"] else ""
            lines.append(f"- **{p['title']}**{addr}")
            if str(p.get("content_type_id")) == "39":  # 맛집·카페: 대표 메뉴 → 취급 메뉴 → 소개글 순
                intro = p.get("intro", {})
                menu = menu_text(intro)
                feature = (menu if intro.get("firstmenu") else f"{menu} (취급 메뉴)" if menu else "") \
                    or one_liner(p.get("overview", ""), 80) or f"{district_of(p['addr']) or label}의 음식점이에요."
            else:
                feature = one_liner(p.get("overview", "")) or f"{district_of(p['addr']) or label}에 있는 {p['content_type']}이에요."
            lines.append(f"  - 💡 {feature}")
            views.append(_view(p, category=cat, summary=feature))
        lines.append("")
    return "\n".join(lines).strip(), views


def render_food(label: str, items: list[dict], cafe: bool) -> tuple[str, list[dict]]:
    kind = "카페" if cafe else "맛집"
    lines, views = [f"## {label} {kind} 추천", ""], []
    for i, p in enumerate(items, 1):
        intro = p.get("intro", {})
        menu = menu_text(intro)
        feature = (menu if intro.get("firstmenu") else f"{menu} (취급 메뉴)" if menu else
                   one_liner(p.get("overview", ""), 80) or f"{district_of(p['addr']) or label}의 {'카페' if cafe else '음식점'}")
        access = access_text(intro)
        lines.append(f"**{i}. {p['title']}**")
        if p["addr"]:
            lines.append(f"- 📍 위치: {p['addr']}")
        lines.append(f"- 🍴 대표 메뉴/특징: {feature}")
        if access:
            lines.append(f"- 🚶 접근성: {access}")
        lines.append("")
        views.append(_view(p, menu=menu, access=access, summary=feature))
    return "\n".join(lines).strip(), views


def _ymd(d: str) -> str:
    d = str(d or "")
    return f"{d[:4]}-{d[4:6]}-{d[6:8]}" if len(d) == 8 and d.isdigit() else d


def render_stay(label: str, items: list[dict]) -> tuple[str, list[dict]]:
    lines, views = [f"## {label} 숙박 추천", ""], []
    for i, p in enumerate(items, 1):
        intro = p.get("intro", {})
        times = lodging_text(intro)
        feature = one_liner(p.get("overview", ""), 90) or f"{district_of(p['addr']) or label}의 숙박시설이에요."
        lines.append(f"**{i}. {p['title']}**")
        if p["addr"]:
            lines.append(f"- 📍 위치: {p['addr']}")
        if times:
            lines.append(f"- 🕒 체크인/아웃·운영 정보: {times}")
        lines.append(f"- 💡 특징: {feature}")
        lines.append("")
        views.append(_view(p, hours=times, summary=feature))
    return "\n".join(lines).strip(), views


def render_festival(label: str, items: list[dict]) -> tuple[str, list[dict]]:
    lines, views = [f"## {label} 축제·행사", ""], []
    for i, p in enumerate(items, 1):
        period = f"{_ymd(p.get('event_start'))} ~ {_ymd(p.get('event_end') or p.get('event_start'))}"
        feature = one_liner(p.get("overview", ""), 90) or f"{district_of(p['addr']) or label}에서 열리는 {p['content_type'] or '행사'}예요."
        lines.append(f"**{i}. {p['title']}**")
        lines.append(f"- 🗓 기간: {period}")
        if p["addr"]:
            lines.append(f"- 📍 위치: {p['addr']}")
        lines.append(f"- 💡 특징: {feature}")
        lines.append("")
        views.append(_view(p, period=period, summary=feature))
    return "\n".join(lines).strip(), views


def render_course(label: str, items: list[dict]) -> tuple[str, list[dict]]:
    lines, views = [f"## {label} 추천 여행코스", ""], []
    for i, p in enumerate(items, 1):
        intro = p.get("intro", {})
        extra = course_text(intro)
        feature = one_liner(p.get("overview", ""), 110) or f"{label}에서 즐기는 추천 여행코스예요."
        lines.append(f"**{i}. {p['title']}**")
        if p["addr"]:
            lines.append(f"- 📍 위치: {p['addr']}")
        if extra:
            lines.append(f"- ⏱ {extra}")
        lines.append(f"- 💡 특징: {feature}")
        lines.append("")
        views.append(_view(p, summary=feature, course=extra))
    return "\n".join(lines).strip(), views


NOT_FOUND = "조건에 맞는 장소를 찾지 못했어요. 지역을 조금 넓혀서(예: '성남', '부산') 다시 말씀해 주시겠어요?"


def answer_list(intent: str, label: str, text: str, places: list[dict], rank, enrich_overview, enrich_intro) -> tuple[str, list[dict], list[str]]:
    """
    Returns: (답변 마크다운, 화면/API용 장소 목록, 개발자 정보용 경고)
    enrich_overview(list) / enrich_intro(list): 선택된 장소에 소개글/메뉴·영업시간을 채우는 함수 (경고 리스트 반환)
    """
    warnings: list[str] = []
    if intent in ("stay", "festival", "course"):
        pool = [p for p in places if str(p.get("content_type_id")) in {"stay": {"32"}, "festival": {"15"}, "course": {"25"}}[intent]]
        items = rank(pool)[:5]
        if not items:
            return NOT_FOUND, [], warnings
        warnings += enrich_overview(items)
        if intent != "festival":
            warnings += enrich_intro(items)  # 숙박: 체크인·아웃, 코스: 소요 시간·거리
        render = {"stay": render_stay, "festival": render_festival, "course": render_course}[intent]
        reply, views = render(label, items)
        return reply, views, warnings
    if intent == "food":
        pool = select_food(places, text, rank, FOOD_POOL)
        if not pool:
            return NOT_FOUND, [], warnings
        warnings += enrich_intro(pool)  # 후보 12곳의 대표메뉴·영업시간을 조회(24시간 저장)한 뒤
        items = sorted(pool, key=lambda p: -info_score(p))[:FOOD_SHOW]  # 정보가 채워진 곳을 우선해 5곳 (동점이면 취향 순위 유지)
        warnings += enrich_overview(items)
        reply, views = render_food(label, items, bool(CAFE_ASK_RE.search(text)))
        return reply, views, warnings
    groups = select_recommend(places, text, rank)
    if not ONLY_SIGHTS_RE.search(text):  # 카테고리별(자연·문화·맛집 등)로 안내: 맛집·카페도 최대 3곳
        pool = select_food(places, text, rank, 6)
        if pool:
            warnings += enrich_intro(pool)
            groups.append(("🍽 맛집·카페", sorted(pool, key=lambda p: -info_score(p))[:3]))
    if not groups:
        return NOT_FOUND, [], warnings
    warnings += enrich_overview([p for _, items in groups for p in items])
    reply, views = render_recommend(label, groups)
    return reply, views, warnings
