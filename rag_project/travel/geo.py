"""
좌표 기반 거리·이동 시간 추정.

TourAPI의 장소 좌표(mapx=경도, mapy=위도)로 직선거리를 구하고, 도로 보정(×1.3)을 해서 이동 시간을 '대략' 추정합니다.
실제 길찾기가 아니라 추정치입니다. AI가 시간을 지어내지 않도록 코드가 계산합니다.
"""
import math

ROAD_FACTOR = 1.3  # 직선거리 → 실제 도로 거리 보정


def _coord(p: dict) -> tuple[float, float] | None:
    try:
        lat, lon = float(p.get("mapy")), float(p.get("mapx"))
    except (TypeError, ValueError):
        return None
    if not (33 <= lat <= 39 and 124 <= lon <= 132):  # 한국 밖이거나 0 같은 값이면 무효
        return None
    return lat, lon


def straight_km(a: dict, b: dict) -> float | None:
    ca, cb = _coord(a), _coord(b)
    if ca is None or cb is None:
        return None
    (la1, lo1), (la2, lo2) = ca, cb
    r = 6371.0
    p1, p2 = math.radians(la1), math.radians(la2)
    dphi, dl = p2 - p1, math.radians(lo2 - lo1)
    h = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def _round5(x: float) -> int:
    return int(5 * round(x / 5))


def estimate_travel(a: dict, b: dict) -> dict:
    """
    Returns:
        {"minutes": 일정에 반영할 이동 시간(분), "text": "도보 약 10분" 등 표시 문구, "km": 도로 기준 거리 또는 None}
    - 1.2km 미만: 도보 / 그 이상: 대중교통·차량 (대중교통 시간을 일정에 반영)
    """
    d = straight_km(a, b)
    if d is None:
        return {"minutes": 20, "text": "이동 약 20분 (거리 정보 없음)", "km": None}
    d *= ROAD_FACTOR
    if d < 1.2:
        walk = max(5, _round5(d / 4.5 * 60))
        return {"minutes": walk, "text": f"도보 약 {walk}분", "km": round(d, 1)}
    car_speed = 28 if d < 10 else 40 if d < 30 else 60
    transit_speed = 18 if d < 10 else 28 if d < 30 else 40
    car = max(5, _round5(5 + d / car_speed * 60))
    transit = max(10, _round5(10 + d / transit_speed * 60))
    return {"minutes": transit, "text": f"대중교통 약 {transit}분 / 차량 약 {car}분", "km": round(d, 1)}


def order_by_proximity(items: list[dict]) -> list[dict]:
    """첫 장소에서 시작해 가장 가까운 곳을 차례로 방문하는 순서로 정렬 (이동을 줄임). 좌표 없는 장소는 뒤에 그대로."""
    with_c = [it for it in items if _coord(it["place"])]
    without = [it for it in items if not _coord(it["place"])]
    if len(with_c) <= 2:
        return with_c + without
    ordered = [with_c[0]]
    rest = with_c[1:]
    while rest:
        last = ordered[-1]["place"]
        nxt = min(rest, key=lambda it: straight_km(last, it["place"]) or 1e9)
        ordered.append(nxt)
        rest.remove(nxt)
    return ordered + without


def district_of(addr: str) -> str:
    """주소에서 시군구 부분을 뽑는다. '경기도 성남시 분당구 성남대로 550' → '성남시 분당구'"""
    toks = (addr or "").split()
    for i, t in enumerate(toks):
        if i >= 1 and t.endswith(("시", "군", "구")):
            if i + 1 < len(toks) and toks[i + 1].endswith("구"):
                return f"{t} {toks[i + 1]}"
            return t
    return ""
