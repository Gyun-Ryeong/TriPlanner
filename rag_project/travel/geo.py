"""
좌표 기반 거리·이동 시간 추정.

TourAPI의 장소 좌표(mapx=경도, mapy=위도)로 직선거리를 구하고, 도로 보정(×1.3)을 해서 이동 시간을 '대략' 추정합니다.
실제 길찾기가 아니라 추정치입니다. AI가 시간을 지어내지 않도록 코드가 계산합니다.
"""
import itertools
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


EXACT_MAX = 7       # 장소가 이 수 이하면 가능한 순서를 전부 비교해 가장 짧은 길을 고른다 (7곳 = 5,040가지)
_NO_DIST_KM = 50.0  # 좌표가 없어 거리를 모를 때 쓰는 값


def _dist_matrix(points: list[dict]) -> list[list[float]]:
    def d(a, b):
        km = straight_km(a, b)
        return _NO_DIST_KM if km is None else km
    return [[0.0 if i == j else d(a, b) for j, b in enumerate(points)] for i, a in enumerate(points)]


def _route_len(order: list[int], m: list[list[float]], base: int | None) -> float:
    """order 순서로 이은 길이. base(숙소)가 있으면 숙소 → … → 숙소."""
    path = ([base] + order + [base]) if base is not None else order
    return sum(m[a][b] for a, b in zip(path, path[1:]))


def _two_opt(order: list[int], m: list[list[float]], base: int | None) -> list[int]:
    """구간을 뒤집어 더 짧아지면 바꾸기를 더 이상 안 줄 때까지 반복 (장소가 많을 때의 근사)"""
    best, best_len, improved = order[:], _route_len(order, m, base), True
    while improved:
        improved = False
        for i in range(len(best) - 1):
            for k in range(i + 1, len(best)):
                cand = best[:i] + best[i:k + 1][::-1] + best[k + 1:]
                cand_len = _route_len(cand, m, base)
                if cand_len < best_len - 1e-9:
                    best, best_len, improved = cand, cand_len, True
    return best


def best_order(items: list[dict], base: dict | None = None) -> list[dict]:
    """
    하루 방문지를 이동거리가 가장 짧은 순서로 정렬합니다. (items: [{"place": 장소}, ...])
    - base(숙소)가 있으면 숙소에서 출발해 숙소로 돌아오는 길, 없으면 어디서 시작해도 되는 한 줄 길
    - EXACT_MAX곳 이하는 모든 순서를 비교(정확), 그보다 많으면 가까운 곳 잇기 + 2-opt(근사)
    - 길이가 같으면 원래 순서(AI가 정한 순서)에 가까운 쪽을 고른다
    - 좌표 없는 장소는 뒤에 그대로
    """
    with_c = [it for it in items if _coord(it["place"])]
    without = [it for it in items if not _coord(it["place"])]
    if len(with_c) <= 1 or (len(with_c) == 2 and base is None):
        return with_c + without
    points = [it["place"] for it in with_c] + ([base] if base is not None and _coord(base) else [])
    b = len(with_c) if len(points) > len(with_c) else None
    m = _dist_matrix(points)
    idx = list(range(len(with_c)))
    if len(idx) <= EXACT_MAX:
        best, best_len = idx, _route_len(idx, m, b)
        for perm in itertools.permutations(idx):  # 사전순이라 같은 길이면 원래 순서에 가까운 것이 먼저 남는다
            ln = _route_len(list(perm), m, b)
            if ln < best_len - 1e-6 or (b is not None and abs(ln - best_len) <= 1e-6 and m[b][perm[0]] < m[b][best[0]] - 1e-9):
                best, best_len = list(perm), ln  # 숙소 왕복은 거꾸로 돌아도 길이가 같다 → 숙소에서 가까운 곳부터
    else:
        start = min(idx, key=lambda i: m[b][i]) if b is not None else 0
        best, rest = [start], [i for i in idx if i != start]
        while rest:
            nxt = min(rest, key=lambda i: m[best[-1]][i])
            best.append(nxt)
            rest.remove(nxt)
        best = _two_opt(best, m, b)
    return [with_c[i] for i in best] + without


def route_km(places: list[dict], base: dict | None = None) -> float:
    """장소들을 이 순서대로 이은 직선거리 합 (숙소가 있으면 숙소 → … → 숙소)"""
    path = ([base] if base else []) + places + ([base] if base else [])
    return sum(d for d in (straight_km(a, b) for a, b in zip(path, path[1:])) if d is not None)


def order_by_proximity(items: list[dict]) -> list[dict]:
    """이동이 가장 짧은 순서 (예전 이름 유지)"""
    return best_order(items)


def order_from(base: dict, items: list[dict]) -> list[dict]:
    """숙소에서 출발해 숙소로 돌아오는 가장 짧은 순서 (예전 이름 유지)"""
    return best_order(items, base)


def district_of(addr: str) -> str:
    """주소에서 시군구 부분을 뽑는다. '경기도 성남시 분당구 성남대로 550' → '성남시 분당구'"""
    toks = (addr or "").split()
    for i, t in enumerate(toks):
        if i >= 1 and t.endswith(("시", "군", "구")):
            if i + 1 < len(toks) and toks[i + 1].endswith("구"):
                return f"{t} {toks[i + 1]}"
            return t
    return ""
