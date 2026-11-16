"""
날짜 사이 장소 맞바꾸기 (동선 최적화 2단계).

AI는 날짜마다 장소를 고르지만 위치를 잘 따지지 못해, 1일차에 북쪽 끝과 남쪽 끝이 같이 들어가곤 합니다.
두 날의 장소를 하나씩 맞바꿔서 각 날의 장소들이 더 가까이 모이면 바꿉니다. (하루 안의 순서는 geo.best_order가 정한다)

- 판단 기준: 각 날 장소들의 '그날 중심점까지 거리' 합 (모일수록 작다). 최단 경로를 매번 계산하는 것보다 훨씬 빠르다
- 움직이지 않는 것: frozen(축제·사용자가 말한 장소 등), 좌표 없는 장소
- 실외 장소는 날씨 나쁜 날로 보내지 않는다
- 맞바꾸기라 날마다 장소 수는 그대로다
"""
from datetime import date

from travel.geo import _coord, straight_km
from travel.hours import WD, closed_on
from travel.places import is_indoor

MIN_GAIN_KM = 1.0   # 이보다 적게 줄면 바꾸지 않는다 (AI가 정한 테마를 괜히 흔들지 않게)
MAX_ROUNDS = 5


def _center(points: list[tuple[float, float]]) -> tuple[float, float] | None:
    if not points:
        return None
    return sum(p[0] for p in points) / len(points), sum(p[1] for p in points) / len(points)


def _spread(places: list[dict]) -> float:
    """장소들이 중심에서 떨어진 거리 합 (km)"""
    pts = [c for c in (_coord(p) for p in places) if c]
    c = _center(pts)
    if c is None:
        return 0.0
    center = {"mapy": c[0], "mapx": c[1]}
    return sum(straight_km(center, p) or 0.0 for p in places if _coord(p))


def _indoor(p: dict) -> bool:
    return bool(p.get("indoor", is_indoor(p)))


def rebalance_days(days: list[dict], cand_map: dict[str, dict], conditions: list[dict], frozen: set[str] | None = None) -> int:
    """
    days: plan["days"] (각 day["items"] = [{"candidate_id", "note"}, ...]) — 제자리에서 고친다
    conditions: 일자별 날씨 (outdoor_ok가 False면 궂은 날)
    Returns: 맞바꾼 횟수
    """
    frozen = frozen or set()
    n = len(days)
    if n < 2:
        return 0

    def places_of(d: int) -> list[dict]:
        return [cand_map[it["candidate_id"]] for it in days[d]["items"] if it.get("candidate_id") in cand_map]

    def movable(it: dict) -> bool:
        cid = it.get("candidate_id")
        return bool(cid) and cid in cand_map and cid not in frozen and _coord(cand_map[cid]) is not None

    def fits(p: dict, d: int) -> bool:
        return _fits(p, d, conditions)

    spread = [_spread(places_of(d)) for d in range(n)]
    swaps = 0
    for _ in range(MAX_ROUNDS):
        changed = False
        for a in range(n):
            for b in range(a + 1, n):
                best = None
                for i, ia in enumerate(days[a]["items"]):
                    if not movable(ia):
                        continue
                    pa = cand_map[ia["candidate_id"]]
                    if not fits(pa, b):
                        continue
                    for j, ib in enumerate(days[b]["items"]):
                        if not movable(ib):
                            continue
                        pb = cand_map[ib["candidate_id"]]
                        if not fits(pb, a):
                            continue
                        new_a = [pb if k == i else p for k, p in enumerate(_items_places(days[a], cand_map))]
                        new_b = [pa if k == j else p for k, p in enumerate(_items_places(days[b], cand_map))]
                        sa, sb = _spread([p for p in new_a if p]), _spread([p for p in new_b if p])
                        gain = spread[a] + spread[b] - sa - sb
                        if gain > MIN_GAIN_KM and (best is None or gain > best[0]):
                            best = (gain, i, j, sa, sb)
                if best:
                    _, i, j, sa, sb = best
                    days[a]["items"][i], days[b]["items"][j] = days[b]["items"][j], days[a]["items"][i]
                    spread[a], spread[b] = sa, sb
                    swaps += 1
                    changed = True
        if not changed:
            break
    return swaps


def _day_date(conditions: list[dict], d: int) -> date | None:
    try:
        return date.fromisoformat(str(conditions[d].get("date", ""))[:10])
    except (ValueError, IndexError):
        return None


def _fits(p: dict, d: int, conditions: list[dict]) -> bool:
    """그날 갈 수 있는지: 실외 장소는 궂은 날 안 되고, 휴무일이면 안 된다"""
    if not _indoor(p) and conditions[d].get("outdoor_ok") is False:
        return False
    dd = _day_date(conditions, d)
    return dd is None or not closed_on(p, dd)


def fix_closures(days: list[dict], cand_map: dict[str, dict], conditions: list[dict],
                 frozen: set[str] | None = None) -> list[str]:
    """
    휴무일에 들어간 장소를 고칩니다 (제자리에서). 순서대로 시도:
      1) 다른 날의 장소와 맞바꾸기 (둘 다 그날 열고 날씨도 맞을 때)
      2) 일정에 안 쓴 후보 중 그날 여는 가까운 곳으로 바꾸기
      3) 그래도 없으면 빼기
    frozen(사용자가 꼭 넣은 장소 등)은 건드리지 않는다.
    Returns: 사용자에게 알릴 문장 목록
    """
    frozen = frozen or set()
    notes: list[str] = []
    used = {it.get("candidate_id") for day in days for it in day["items"]}

    def label(d: int) -> str:
        dd = _day_date(conditions, d)
        return f"{dd.month}/{dd.day}({WD[dd.weekday()]})" if dd else f"{d + 1}일차"

    def near_center(d: int, p: dict) -> float:
        others = [cand_map[it["candidate_id"]] for it in days[d]["items"] if it.get("candidate_id") in cand_map]
        pts = [c for c in (_coord(o) for o in others) if c]
        c = _center(pts)
        return straight_km({"mapy": c[0], "mapx": c[1]}, p) or 0.0 if c else 0.0

    for d, day in enumerate(days):
        dd = _day_date(conditions, d)
        if dd is None:
            continue
        for it in list(day["items"]):
            cid = it.get("candidate_id")
            p = cand_map.get(cid) if cid else None
            if p is None or cid in frozen or not closed_on(p, dd):
                continue
            i = next(k for k, x in enumerate(day["items"]) if x is it)  # 앞에서 뺀 항목이 있으면 위치가 바뀐다
            # 1) 다른 날과 맞바꾸기
            swap = None
            for e, other in enumerate(days):
                if e == d or not _fits(p, e, conditions):
                    continue
                for j, ot in enumerate(other["items"]):
                    q = cand_map.get(ot.get("candidate_id"))
                    if q is None or ot.get("candidate_id") in frozen or not _fits(q, d, conditions):
                        continue
                    score = near_center(d, q) + near_center(e, p)
                    if swap is None or score < swap[0]:
                        swap = (score, e, j)
            if swap:
                _, e, j = swap
                day["items"][i], days[e]["items"][j] = days[e]["items"][j], day["items"][i]
                notes.append(f"{p['title']}은(는) {label(d)} 휴무라 {label(e)}로 옮겼어요")
                continue
            # 2) 안 쓴 후보로 바꾸기
            spare = [(near_center(d, q), c) for c, q in cand_map.items()
                     if c not in used and q.get("content_type_id") != "15" and _fits(q, d, conditions)]
            if spare:
                _, c = min(spare)
                day["items"][i] = {**it, "candidate_id": c, "note": ""}
                used.add(c)
                notes.append(f"{p['title']}은(는) {label(d)} 휴무라 {cand_map[c]['title']}(으)로 바꿨어요")
                continue
            # 3) 빼기
            day["items"] = [x for x in day["items"] if x is not it]
            notes.append(f"{p['title']}은(는) {label(d)} 휴무라 일정에서 뺐어요")
    return notes


def _items_places(day: dict, cand_map: dict[str, dict]) -> list[dict | None]:
    """day["items"]와 같은 순서·길이의 장소 목록 (후보가 아닌 항목은 None)"""
    return [cand_map.get(it.get("candidate_id")) if it.get("candidate_id") else None for it in day["items"]]
