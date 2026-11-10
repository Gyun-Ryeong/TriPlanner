"""
네이버 지역(장소) 검색 API (NAVER API HUB, 뉴스와 같은 키)

사용자가 직접 말한 카페·식당·숙소처럼 TourAPI에 없는 장소의 이름 → 주소·좌표를 찾는 데 씁니다.
응답의 mapx/mapy 는 경도·위도에 10^7을 곱한 정수 문자열이라(예: 1270782336) 도(°)로 바꿔 TourAPI 장소와 같은 형식으로 돌려줍니다.
"""
from collectors.cache import ttl_cache
from collectors.naver_news import _call, _clean, _raise_for_error
from config import ENDPOINTS


def _deg(v: str) -> str:
    try:
        return f"{int(v) / 1e7:.7f}"
    except (TypeError, ValueError):
        return ""


@ttl_cache("naver_local", 24 * 3600, stale_ttl=7 * 24 * 3600, fail_cooldown=120)
def search_local(query: str, display: int = 5) -> list[dict]:
    """
    장소 검색 (display 최대 5).

    Returns: [{"title", "category", "addr"(도로명 우선), "mapx"(경도), "mapy"(위도), "telephone", "link"}]
    """
    resp = _call("GET", ENDPOINTS["naver_local_hub"], params={"query": query, "display": min(display, 5), "sort": "random"})
    _raise_for_error(resp)
    out = []
    for it in resp.json().get("items", []):
        out.append({
            "source": "naver_local",
            "title": _clean(it.get("title", "")),
            "category": it.get("category", ""),
            "addr": it.get("roadAddress") or it.get("address", ""),
            "mapx": _deg(it.get("mapx")),
            "mapy": _deg(it.get("mapy")),
            "telephone": it.get("telephone", ""),
            "link": it.get("link", ""),
        })
    return out
