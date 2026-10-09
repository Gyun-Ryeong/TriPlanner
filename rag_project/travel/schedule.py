"""
하루 시간표 생성.

AI가 정한 '그날 방문할 장소 순서'를 받아서, 코드가 다음을 채웁니다.
  - 장소별 시작/종료 시각 (유형별 체류 시간)
  - 장소 사이의 이동 수단과 예상 시간 (좌표 기반 추정)
  - 점심(12시 무렵)·저녁(18시 무렵): 직전 장소에서 가장 가까운 음식점(TourAPI 음식점 목록)
AI는 시각·이동·식당을 정하지 않으므로 지어낼 수 없습니다.
"""
from travel.geo import estimate_travel, order_by_proximity, straight_km

DAY_START = 10 * 60
LUNCH_EARLIEST, LUNCH_MIN = 12 * 60, 70
DINNER_EARLIEST, DINNER_MIN = 18 * 60, 80
MIN_FREE_GAP = 30  # 이 이상 비면 '자유 시간'으로 표시

# 장소 유형별 체류 시간(분)
STAY_MIN = {"12": 90, "14": 100, "15": 120, "28": 120, "38": 60, "25": 120}
DEFAULT_STAY = 90


def hhmm(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def stay_minutes(place: dict) -> int:
    return STAY_MIN.get(str(place.get("content_type_id", "")), DEFAULT_STAY)


def pick_restaurant(prev: dict | None, restaurants: list[dict], used: set[str]) -> dict | None:
    """아직 쓰지 않은 음식점 중 직전 장소에서 가장 가까운 곳. 순위(취향 유사도) 상위 30곳 안에서 고른다."""
    pool = [r for r in restaurants[:30] if (r.get("content_id") or r.get("title")) not in used]
    if not pool:
        return None
    if prev is None:
        return pool[0]
    with_dist = [(straight_km(prev, r), i, r) for i, r in enumerate(pool)]
    known = [x for x in with_dist if x[0] is not None]
    if not known:
        return pool[0]
    return min(known, key=lambda x: (x[0], x[1]))[2]


def build_timeline(day_items: list[dict], restaurants: list[dict], used_restaurants: set[str]) -> list[dict]:
    """
    Args:
        day_items: [{"place": place_dict, "note": str}, ...] 그날 방문할 장소 (순서는 여기서 가까운 순으로 다시 정렬)
        restaurants: 취향 유사도 순으로 정렬된 음식점
        used_restaurants: 다른 날에 이미 쓴 음식점 (여기에 이번에 쓴 것도 추가됨)
    Returns:
        이벤트 리스트. kind = visit | move | meal | free
    """
    events: list[dict] = []
    t = DAY_START
    prev: dict | None = None
    lunch_done = False

    def move_to(frm, to, earliest=None):
        """frm→to 이동을 추가. earliest가 있으면 그 시각 이후 도착하도록 출발을 늦추고(빈 시간은 자유 시간), 도착 시각을 돌려준다."""
        nonlocal t
        est = estimate_travel(frm, to) if frm is not None else {"minutes": 0, "text": ""}
        m = est["minutes"]
        if earliest is not None and t + m < earliest:
            depart = earliest - m
            if depart - t >= MIN_FREE_GAP:
                events.append({"kind": "free", "start": hhmm(t), "end": hhmm(depart), "text": "자유 시간 (주변 산책·카페 휴식)"})
                t = depart
            else:
                earliest = t + m  # 짧은 틈은 그냥 일찍 도착
        if frm is not None and m:
            events.append({"kind": "move", "start": hhmm(t), "end": hhmm(t + m), "from": frm, "to": to, "text": est["text"]})
            t += m
        if earliest is not None and t < earliest:
            t = earliest

    def meal(label: str, earliest: int, minutes: int):
        nonlocal t, prev
        r = pick_restaurant(prev, restaurants, used_restaurants)
        if r is not None:
            used_restaurants.add(r.get("content_id") or r.get("title"))
            move_to(prev, r, earliest)
        elif t < earliest:
            if earliest - t >= MIN_FREE_GAP:
                events.append({"kind": "free", "start": hhmm(t), "end": hhmm(earliest), "text": "자유 시간 (주변 산책·카페 휴식)"})
            t = earliest
        events.append({"kind": "meal", "label": label, "start": hhmm(t), "end": hhmm(t + minutes), "place": r})
        t += minutes
        if r is not None:
            prev = r

    ordered = order_by_proximity(day_items)
    for idx, it in enumerate(ordered):
        p = it["place"]
        if not lunch_done and idx > 0:
            m_next = estimate_travel(prev, p)["minutes"] if prev is not None else 0
            # 지금 점심을 먹지 않으면 이 장소가 끝나는 시각이 13:30을 넘어가는 경우, 먼저 점심
            if t >= 11 * 60 + 30 or t + m_next + stay_minutes(p) > 13 * 60 + 30:
                meal("점심", LUNCH_EARLIEST, LUNCH_MIN)
                lunch_done = True
        if prev is not None:
            move_to(prev, p)
        dur = stay_minutes(p)
        events.append({"kind": "visit", "start": hhmm(t), "end": hhmm(t + dur), "place": p, "note": it.get("note", "")})
        t += dur
        prev = p

    if not lunch_done and prev is not None and t < 15 * 60:
        meal("점심", LUNCH_EARLIEST, LUNCH_MIN)
    if prev is not None and t < 20 * 60:
        meal("저녁", DINNER_EARLIEST, DINNER_MIN)
    return events
