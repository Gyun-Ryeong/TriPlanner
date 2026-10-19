"""
지역 대표 사진. 여행 목록에서 '내가 가는 지역'의 사진을 보여주기 위해 TourAPI 관광지 사진 중 하나를 고릅니다.

- 시·군·구를 알면 그 시군구의 관광지만 받습니다 (일정 후보 수집과 같은 호출이라 캐시를 함께 씀)
- 자연(NA) → 역사(HS) → 문화·도시(VE) 관광지 순으로, 사진이 있는 곳을 고릅니다. 체험·먹거리 마을은 피합니다.
- 사진은 한국관광공사 TourAPI 제공 (화면에 출처를 표시)
"""
import threading

from collectors.tourism import get_tourism_info
from config import TOUR_AREA_ROWS
from travel.gazetteer import lookup_in_sido
from travel.ldong import resolve_ldong, resolve_sigungu
from travel.regions import SIDO, normalize_region

# 앱의 권역 이름(새 여행 화면) → 그 권역의 시도. 같은 이름의 시군구(고성 등)를 어느 시도에서 찾을지 고를 때 쓴다
APP_REGION_SIDO = {
    "서울특별시": ["서울"], "경기도/인천": ["경기", "인천"], "강원도": ["강원"], "충청도": ["충북", "충남", "대전", "세종"],
    "전라도": ["전북", "전남", "광주"], "경상도": ["경북", "경남", "부산", "대구", "울산"], "제주도": ["제주"],
}
_CATEGORY_ORDER = {"NA": 0, "HS": 1, "VE": 2}
_SKIP_CATEGORIES = {"EX", "VE04"}  # 체험, 먹거리·특화 마을
_cache: dict[tuple[str, str], dict] = {}
_lock = threading.Lock()


def _resolve(name: str, region: str) -> tuple[str | None, str]:
    """(시도, 시군구 이름). 권역(region)을 주면 그 권역의 시도 안에서 먼저 찾는다."""
    from travel.chat import resolve_place_ext  # 순환 import 방지

    name = (name or "").strip()
    text = f"{name} 여행"  # 지명 하나만 받으므로 일상 단어와 같은 이름(광명, 이천)도 지명으로 읽게 여행 문맥을 붙인다
    hint = APP_REGION_SIDO.get((region or "").replace(" ", ""), [])
    if not hint and normalize_region(region or ""):
        hint = [normalize_region(region)]
    for sido in hint:
        area = lookup_in_sido(text, sido)
        if area:
            return sido, area
        if sido == normalize_region(name):  # '부산', '서울'처럼 시도 자체가 도시
            return sido, ""
    sido, area = resolve_place_ext(text)
    if sido and (not hint or sido in hint):
        return sido, area
    return (hint[0], "") if hint else (None, "")


def _pick(places: list[dict]) -> dict | None:
    def rank(p):
        raw = p.get("raw") or {}
        return _CATEGORY_ORDER.get(raw.get("lclsSystm1", ""), 3)

    pool = [p for p in places if p.get("image") and p.get("content_type_id") == "12"
            and not ({(p.get("raw") or {}).get("lclsSystm1"), (p.get("raw") or {}).get("lclsSystm2")} & _SKIP_CATEGORIES)]
    if not pool:
        pool = [p for p in places if p.get("image") and p.get("content_type_id") in ("12", "14")]
    return min(pool, key=rank) if pool else None  # min은 같은 순위면 앞(최근 수정)것을 고른다


def region_photo(name: str, region: str = "") -> dict:
    """
    Returns: {"sido", "area", "image"(없으면 ""), "title"(사진 속 장소), "credit"}
    외부 호출이 실패해도 예외를 던지지 않고 image를 빈 값으로 돌려줍니다.
    """
    sido, area = _resolve(name, region)
    out = {"sido": sido or "", "area": area, "image": "", "title": "", "credit": "한국관광공사 TourAPI"}
    if not sido or sido not in SIDO:
        return out
    key = (sido, area)
    with _lock:
        if key in _cache:
            return {**out, **_cache[key]}
    try:
        code, _shared = resolve_ldong(sido)
        places: list[dict] = []
        for _name, scode in (resolve_sigungu(sido, area) if area else []):
            places += get_tourism_info(l_dong_regn_cd=code, l_dong_signgu_cd=scode, num_rows=TOUR_AREA_ROWS)
        if not places:
            places = get_tourism_info(l_dong_regn_cd=code, content_type_id="12", num_rows=100)
            if area:
                places = [p for p in places if area in p["addr"]] or places
    except Exception:
        return out  # 실패는 기억하지 않아 다음에 다시 시도
    best = _pick(places)
    found = {"image": best["image"].replace("http://", "https://", 1), "title": best["title"]} if best else {"image": "", "title": ""}
    with _lock:
        _cache[key] = found
    return {**out, **found}
