"""
한국문화정보원_한눈에보는문화정보조회서비스 (전국 문화축제 정보 등)
"""
from config import ENDPOINTS
from collectors.base_client import call_public_api, extract_items


def get_culture_info(keyword: str = "", num_rows: int = 10) -> list[dict]:
    """
    문화행사/축제 정보를 조회합니다.

    Args:
        keyword: 검색 키워드 (제목 기준). 비우면 전체 최신순.
        num_rows: 가져올 개수
    """
    params = {
        "numOfRows": num_rows,
        "pageNo": 1,
    }
    if keyword:
        params["keyword"] = keyword

    parsed = call_public_api(ENDPOINTS["culture"], params)
    items = extract_items(parsed)

    results = []
    for item in items:
        results.append({
            "source": "culture",
            "title": item.get("title", item.get("subject", "")),
            "period": item.get("period", ""),
            "place": item.get("place", item.get("eventSite", "")),
            "raw": item,
        })
    return results
