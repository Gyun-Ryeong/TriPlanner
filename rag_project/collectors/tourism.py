"""
한국관광공사_국문 관광정보 서비스_GW (KorService2)
- 지역기반 관광정보 목록 (areaBasedList2)
- 행사/축제 검색 (searchFestival2)
- 장소 소개글 (detailCommon2)

※ 지역 필터는 법정동 시도 코드(lDongRegnCd)를 사용합니다.
   예전 areaCode 파라미터는 값이 비어 있는 관광지가 많아 대표 관광지가 빠질 수 있습니다.
"""
import html
import json
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from config import ENDPOINTS, OVERVIEW_CACHE_PATH
from collectors.base_client import call_public_api, extract_items
from collectors.cache import ttl_cache

CONTENT_TYPE_NAMES = {
    "12": "관광지",
    "14": "문화시설",
    "15": "축제공연행사",
    "25": "여행코스",
    "28": "레포츠",
    "32": "숙박",
    "38": "쇼핑",
    "39": "음식점",
}

_APP_PARAMS = {"MobileOS": "ETC", "MobileApp": "TriPlanner"}


def _to_place(item: dict) -> dict:
    ctype = str(item.get("contenttypeid", ""))
    addr = " ".join(x for x in [item.get("addr1", ""), item.get("addr2", "")] if x).strip()
    return {
        "source": "tourism",
        "content_id": str(item.get("contentid", "")),
        "title": (item.get("title") or "").strip(),
        "addr": addr,
        "content_type_id": ctype,
        "content_type": CONTENT_TYPE_NAMES.get(ctype, ctype),
        "mapx": str(item.get("mapx", "")),
        "mapy": str(item.get("mapy", "")),
        "image": item.get("firstimage", "") or "",
        "modified_time": item.get("modifiedtime", ""),
        "event_start": str(item.get("eventstartdate", "")),
        "event_end": str(item.get("eventenddate", "")),
        "overview": "",
        "raw": item,
    }


@ttl_cache("tourism", 12 * 3600, stale_ttl=7 * 24 * 3600)
def get_tourism_info(
    l_dong_regn_cd: str = "",
    content_type_id: str = "",
    num_rows: int = 10,
    page: int = 1,
    area_code: str = "",
    l_dong_signgu_cd: str = "",
) -> list[dict]:
    """
    시도/콘텐츠타입 기반 관광정보를 조회합니다.

    Args:
        l_dong_regn_cd: 법정동 시도 코드 (서울=11, 부산=26, 제주=50 ...). 비우면 전국.
        content_type_id: 12=관광지, 14=문화시설, 15=축제공연행사, 28=레포츠, 39=음식점 등
        num_rows: 가져올 개수
        page: 페이지 번호
        area_code: (구 방식) 시도 코드. l_dong_regn_cd가 없을 때만 사용. 비교/폴백용.
        l_dong_signgu_cd: 법정동 시군구 코드(예: 성남시 분당구). l_dong_regn_cd와 함께 쓰며, 시군구 단위는 수백 건이라 한 번에 전부 받을 수 있음.
    """
    params = {**_APP_PARAMS, "numOfRows": num_rows, "pageNo": page, "arrange": "C"}
    if l_dong_regn_cd:
        params["lDongRegnCd"] = l_dong_regn_cd
        if l_dong_signgu_cd:
            params["lDongSignguCd"] = l_dong_signgu_cd
    elif area_code:
        params["areaCode"] = area_code
    if content_type_id:
        params["contentTypeId"] = content_type_id

    parsed = call_public_api(ENDPOINTS["tourism"], params)
    return [_to_place(it) for it in extract_items(parsed)]


@ttl_cache("festival", 6 * 3600, stale_ttl=3 * 24 * 3600)
def get_festivals(
    l_dong_regn_cd: str = "",
    start_date: str = "",
    end_date: str = "",
    num_rows: int = 30,
) -> list[dict]:
    """
    행사/축제 검색.

    Args:
        start_date: 'YYYY-MM-DD' 또는 'YYYYMMDD' (행사 시작일 기준 조회 시작일, 필수에 가까움)
        end_date: 'YYYY-MM-DD' 또는 'YYYYMMDD' (선택)
    """
    params = {**_APP_PARAMS, "numOfRows": num_rows, "pageNo": 1, "arrange": "C"}
    if start_date:
        params["eventStartDate"] = start_date.replace("-", "")
    if end_date:
        params["eventEndDate"] = end_date.replace("-", "")
    if l_dong_regn_cd:
        params["lDongRegnCd"] = l_dong_regn_cd

    parsed = call_public_api(ENDPOINTS["tour_festival"], params)
    places = [_to_place(it) for it in extract_items(parsed)]
    for p in places:
        if not p["content_type"] or p["content_type"] == p["content_type_id"]:
            p["content_type"] = "축제공연행사"
    return places


# ── 장소 소개글 (detailCommon2) + 파일 캐시 ───────────────────────────
_cache_lock = threading.Lock()
_overview_cache: dict[str, str] | None = None


def _load_cache() -> dict[str, str]:
    global _overview_cache
    if _overview_cache is None:
        path = Path(OVERVIEW_CACHE_PATH)
        try:
            _overview_cache = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        except Exception:
            _overview_cache = {}
    return _overview_cache


def _save_cache() -> None:
    path = Path(OVERVIEW_CACHE_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _cache_lock:
        path.write_text(json.dumps(_load_cache(), ensure_ascii=False), encoding="utf-8")


def _clean_text(text: str) -> str:
    text = html.unescape(text or "")
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def get_overview(content_id: str) -> str:
    """장소 소개글을 조회합니다 (detailCommon2). 실패 시 예외 발생."""
    params = {**_APP_PARAMS, "contentId": content_id, "numOfRows": 1, "pageNo": 1}
    parsed = call_public_api(ENDPOINTS["tour_detail"], params)
    items = extract_items(parsed)
    if not items:
        return ""
    return _clean_text(items[0].get("overview", ""))


def enrich_overviews(places: list[dict], limit: int) -> list[str]:
    """
    places의 'overview' 필드를 채웁니다. 캐시에 있으면 API를 호출하지 않습니다.

    Args:
        limit: 이번 호출에서 새로 API를 부를 최대 건수 (0이면 캐시만 사용)
    Returns:
        경고 메시지 리스트
    """
    warnings: list[str] = []
    cache = _load_cache()

    todo = []
    for p in places:
        cid = p["content_id"]
        if cid in cache:
            p["overview"] = cache[cid]
        elif cid:
            todo.append(p)

    todo = todo[: max(limit, 0)]
    if not todo:
        return warnings

    # 첫 건을 먼저 호출해 보고, 실패하면 나머지는 호출하지 않음 (파라미터 오류로 한도만 소모하는 것 방지)
    first = todo[0]
    try:
        first["overview"] = get_overview(first["content_id"])
        cache[first["content_id"]] = first["overview"]
    except Exception as e:
        warnings.append(f"장소 소개글 조회 실패로 소개글 없이 진행합니다 ({type(e).__name__}: {str(e)[:100]})")
        return warnings

    def work(p):
        try:
            return p, get_overview(p["content_id"])
        except Exception:
            return p, None

    failed = 0
    with ThreadPoolExecutor(max_workers=6) as ex:
        for p, ov in ex.map(work, todo[1:]):
            if ov is None:
                failed += 1
            else:
                p["overview"] = ov
                cache[p["content_id"]] = ov
    if failed:
        warnings.append(f"장소 소개글 {failed}건 조회 실패")
    _save_cache()
    return warnings


# ── 법정동 시도 코드 목록 (ldongCode2) ────────────────────────────────
def fetch_ldong_regions() -> dict[str, str]:
    """
    시도 이름 → 법정동 시도 코드. 예: {'서울특별시': '11', '부산광역시': '26', ...}
    응답 필드명이 달라도 동작하도록 code/name 계열 키를 유연하게 찾습니다.
    """
    params = {**_APP_PARAMS, "numOfRows": 100, "pageNo": 1}
    parsed = call_public_api(ENDPOINTS["tour_ldong"], params)
    out: dict[str, str] = {}
    for it in extract_items(parsed):
        low = {str(k).lower(): v for k, v in it.items()}
        code = next((str(low[k]) for k in ("ldongregncd", "code", "regncd") if low.get(k) not in (None, "")), "")
        name = next((str(low[k]) for k in ("ldongregnnm", "name", "regnnm") if low.get(k) not in (None, "")), "")
        if code and name:
            out[name] = code
    return out


@ttl_cache("ldong_sigungu", 7 * 24 * 3600)
def fetch_ldong_sigungu(regn_cd: str) -> dict[str, str]:
    """시도 코드 아래의 시군구 이름 → 법정동 시군구 코드. 예: {'성남시 분당구': '135', ...} (ldongCode2에 lDongRegnCd를 주면 구군 목록)"""
    params = {**_APP_PARAMS, "lDongRegnCd": regn_cd, "numOfRows": 300, "pageNo": 1}
    parsed = call_public_api(ENDPOINTS["tour_ldong"], params)
    out: dict[str, str] = {}
    for it in extract_items(parsed):
        low = {str(k).lower(): v for k, v in it.items()}
        code = next((str(low[k]) for k in ("ldongsigngucd", "code", "signgucd") if low.get(k) not in (None, "")), "")
        name = next((str(low[k]) for k in ("ldongsigngunm", "name", "signgunm") if low.get(k) not in (None, "")), "")
        if code and name:
            out[name] = code
    return out


# ── 소개 정보 (detailIntro2): 음식점 대표메뉴·영업시간·휴무·주차 ───────────
@ttl_cache("intro", 24 * 3600)
def get_intro(content_id: str, content_type_id: str) -> dict:
    """장소 유형별 소개 정보. 음식점(39)은 firstmenu/treatmenu/opentimefood/restdatefood/parkingfood 등. 값이 있는 필드만 돌려줍니다."""
    params = {**_APP_PARAMS, "contentId": content_id, "contentTypeId": content_type_id, "numOfRows": 1, "pageNo": 1}
    items = extract_items(call_public_api(ENDPOINTS["tour_intro"], params))
    if not items:
        return {}
    return {k: _clean_text(str(v)) for k, v in items[0].items() if v not in (None, "") and _clean_text(str(v))}


def enrich_intro(places: list[dict], limit: int = 8) -> list[str]:
    """places의 'intro' 필드를 채웁니다 (병렬, 24시간 저장). 개발계정은 하루 호출 한도가 있어 limit으로 제한. 경고 메시지 리스트를 돌려줌."""
    warnings: list[str] = []
    todo = [p for p in places if p.get("content_id")][: max(limit, 0)]
    if not todo:
        return warnings
    first = todo[0]
    try:
        first["intro"] = get_intro(first["content_id"], first["content_type_id"])
    except Exception as e:  # 첫 호출이 실패하면 나머지는 부르지 않는다 (한도만 소모하는 것 방지)
        warnings.append(f"소개 정보 조회 실패로 메뉴·영업시간 없이 진행합니다 ({type(e).__name__}: {str(e)[:100]})")
        return warnings

    def work(p):
        try:
            return p, get_intro(p["content_id"], p["content_type_id"])
        except Exception:
            return p, None

    failed = 0
    with ThreadPoolExecutor(max_workers=5) as ex:
        for p, intro in ex.map(work, todo[1:]):
            if intro is None:
                failed += 1
            else:
                p["intro"] = intro
    if failed:
        warnings.append(f"소개 정보 {failed}건 조회 실패")
    return warnings


def menu_text(intro: dict) -> str:
    """대표 메뉴(없으면 취급 메뉴)."""
    first, treat = (intro or {}).get("firstmenu", ""), (intro or {}).get("treatmenu", "")
    if first:
        return first[:80]
    return treat[:80]


def access_text(intro: dict) -> str:
    """접근성 관련 정보: 주차 · 영업시간 · 휴무일 (있는 것만)."""
    intro = intro or {}
    parts = []
    parking = intro.get("parkingfood") or intro.get("parking")
    if parking:
        parts.append(f"주차 {parking}")
    opening = intro.get("opentimefood") or intro.get("usetime")
    if opening:
        parts.append(f"영업 {opening}")
    rest = intro.get("restdatefood") or intro.get("restdate")
    if rest:
        parts.append(f"휴무 {rest}")
    return " · ".join(parts)[:140]


@ttl_cache("search", 6 * 3600, stale_ttl=3 * 24 * 3600)
def search_places(keyword: str, l_dong_regn_cd: str = "", l_dong_signgu_cd: str = "", num_rows: int = 30) -> list[dict]:
    """장소 이름으로 검색 (searchKeyword2). 지역 코드를 주면 그 지역 안에서만 찾습니다."""
    params = {**_APP_PARAMS, "keyword": keyword, "numOfRows": num_rows, "pageNo": 1, "arrange": "A"}
    if l_dong_regn_cd:
        params["lDongRegnCd"] = l_dong_regn_cd
        if l_dong_signgu_cd:
            params["lDongSignguCd"] = l_dong_signgu_cd
    return [_to_place(it) for it in extract_items(call_public_api(ENDPOINTS["tour_search"], params))]


# detailIntro2는 같은 사실(운영시간·휴무일)을 장소 유형마다 다른 필드 이름으로 줍니다.
_HOURS_FIELDS = {
    "12": ("usetime", "restdate"),                      # 관광지
    "14": ("usetimeculture", "restdateculture"),        # 문화시설
    "28": ("usetimeleports", "restdateleports"),        # 레포츠
    "38": ("opentime", "restdateshopping"),             # 쇼핑
    "39": ("opentimefood", "restdatefood"),             # 음식점
    "32": ("checkintime", "checkouttime"),              # 숙박 (체크인/체크아웃)
}


def operating_text(intro: dict, content_type_id: str) -> str:
    """영업/운영 시간과 휴무일 (유형별 필드에서 있는 것만). 예: '영업 11:00~21:00 · 휴무 매주 월요일'"""
    intro = intro or {}
    open_key, rest_key = _HOURS_FIELDS.get(str(content_type_id), ("usetime", "restdate"))
    parts = []
    if str(content_type_id) == "32":
        return lodging_text(intro)
    if str(content_type_id) == "25":
        return course_text(intro)
    hours = intro.get(open_key) or intro.get("usetime") or intro.get("opentimefood")
    if hours:
        parts.append(f"{'영업' if str(content_type_id) == '39' else '운영'} {hours}")
    rest = intro.get(rest_key) or intro.get("restdate") or intro.get("restdatefood")
    if rest:
        parts.append(f"휴무 {rest}")
    if str(content_type_id) == "15":  # 행사
        if intro.get("playtime"):
            parts.append(f"공연 시간 {intro['playtime']}")
    return " · ".join(parts)[:200]


def lodging_text(intro: dict) -> str:
    """숙박(32): 체크인·체크아웃 시각 (+주차). 예: '체크인 15:00 · 체크아웃 11:00 · 주차 가능'"""
    intro = intro or {}
    parts = []
    if intro.get("checkintime"):
        parts.append(f"체크인 {intro['checkintime']}")
    if intro.get("checkouttime"):
        parts.append(f"체크아웃 {intro['checkouttime']}")
    if intro.get("parkinglodging"):
        parts.append(f"주차 {intro['parkinglodging']}")
    return " · ".join(parts)[:140]


def course_text(intro: dict) -> str:
    """추천 여행코스(25): 소요 시간·거리. 예: '소요 시간 3시간 · 거리 5km'"""
    intro = intro or {}
    parts = []
    if intro.get("taketime"):
        parts.append(f"소요 시간 {intro['taketime']}")
    if intro.get("distance"):
        parts.append(f"거리 {intro['distance']}")
    return " · ".join(parts)[:140]
