"""
국토교통부_한국건설기술연구원 교통량 통계 데이터 정보조회서비스
"""
from config import ENDPOINTS
from collectors.base_client import call_public_api, extract_items


def get_traffic_volume(std_year: str = "", spot_num: str = "", num_rows: int = 20) -> list[dict]:
    """
    교통량 통계 데이터를 조회합니다.

    Args:
        std_year: 기준연도 (예: "2024"). 비우면 API 기본값 사용.
        spot_num: 조사지점번호 (특정 지점만 볼 때)
        num_rows: 가져올 개수
    """
    params = {
        "numOfRows": num_rows,
        "pageNo": 1,
    }
    if std_year:
        params["stdYear"] = std_year
    if spot_num:
        params["spotNum"] = spot_num

    parsed = call_public_api(ENDPOINTS["traffic"], params)
    items = extract_items(parsed)

    results = []
    for item in items:
        results.append({
            "source": "traffic",
            "spot_name": item.get("spotNm", item.get("spotNum", "")),
            "road_name": item.get("routeNm", ""),
            "std_year": item.get("stdYear", std_year),
            "traffic_volume": item.get("trfclum", item.get("trafficVolume", "")),
            "raw": item,
        })
    return results
