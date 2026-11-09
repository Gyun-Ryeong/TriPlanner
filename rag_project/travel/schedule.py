"""
하루 시간표 생성.

AI가 정한 '그날 방문할 장소 순서'를 받아서, 코드가 다음을 채웁니다.
  - 장소별 시작/종료 시각 (유형별 체류 시간)
  - 장소 사이의 이동 수단과 예상 시간 (좌표 기반 추정)
  - 점심(12시 무렵)·저녁(18시 무렵): 직전 장소에서 가장 가까운 음식점(TourAPI 음식점 목록)
AI는 시각·이동·식당을 정하지 않으므로 지어낼 수 없습니다.

시간이 정해진 장소(축제 등: day_items 항목의 "fixed": (시작 분, 끝 분))가 있으면 그 시각은 그대로 두고,
그 앞뒤 빈 시간에 나머지 장소·식사를 맞춰 넣습니다.
"""
from travel.geo import estimate_travel, order_by_proximity, order_from, straight_km

DAY_START = 10 * 60
LUNCH_EARLIEST, LUNCH_MIN = 12 * 60, 70
DINNER_EARLIEST, DINNER_MIN = 18 * 60, 80
MIN_FREE_GAP = 30  # 이 이상 비면 '자유 시간'으로 표시
LATEST_FREE_VISIT = 20 * 60 + 30  # 시간이 정해진 장소가 있는 날, 이 시각 이후에 시작하게 되는 일반 장소는 뺀다

# 장소 유형별 체류 시간(분)
STAY_MIN = {"12": 90, "14": 100, "15": 120, "28": 120, "38": 60, "25": 120}
DEFAULT_STAY = 90


def hhmm(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def stay_minutes(place: dict) -> int:
    if place.get("stay_min"):  # 사용자가 직접 말한 장소(카페 60분 등)는 장소에 체류 시간이 들어 있다
        return int(place["stay_min"])
    return STAY_MIN.get(str(place.get("content_type_id", "")), DEFAULT_STAY)


def pick_restaurant(prev: dict | None, restaurants: list[dict], used: set[str]) -> dict | None:
    """아직 쓰지 않은 음식점 중 직전 장소에서 가장 가까운 곳. 넘겨받은 음식점(취향 유사도 상위, 긴 일정일수록 많이) 안에서 고른다."""
    pool = [r for r in restaurants if (r.get("content_id") or r.get("title")) not in used]
    if not pool:
        return None
    if prev is None:
        return pool[0]
    with_dist = [(straight_km(prev, r), i, r) for i, r in enumerate(pool)]
    known = [x for x in with_dist if x[0] is not None]
    if not known:
        return pool[0]
    return min(known, key=lambda x: (x[0], x[1]))[2]


class _Day:
    """하루의 이벤트를 시간 순서대로 쌓는 작업대. 현재 시각(t)과 직전 장소(prev)를 기억한다."""

    def __init__(self, restaurants: list[dict], used: set[str], base: dict | None = None):
        self.events: list[dict] = []
        self.t = DAY_START
        self.prev: dict | None = None
        self.base = base  # 숙소: 하루의 출발·복귀 지점 (첫 이동과 마지막 복귀 이동이 여기서 시작/끝난다)
        self.restaurants, self.used = restaurants, used
        self.lunch_done = self.dinner_done = False

    def move_to(self, to: dict, earliest: int | None = None) -> None:
        """prev→to 이동을 추가. earliest가 있으면 그 시각 이후 도착하도록 출발을 늦추고(빈 시간은 자유 시간)한다."""
        frm = self.prev
        est = estimate_travel(frm, to) if frm is not None else {"minutes": 0, "text": ""}
        m = est["minutes"]
        if earliest is not None and self.t + m < earliest:
            depart = earliest - m
            if depart - self.t >= MIN_FREE_GAP:
                self.events.append({"kind": "free", "start": hhmm(self.t), "end": hhmm(depart), "text": "자유 시간 (주변 산책·카페 휴식)"})
                self.t = depart
            else:
                earliest = self.t + m  # 짧은 틈은 그냥 일찍 도착
        if frm is not None and m:
            self.events.append({"kind": "move", "start": hhmm(self.t), "end": hhmm(self.t + m), "from": frm, "to": to, "text": est["text"]})
            self.t += m
        if earliest is not None and self.t < earliest:
            self.t = earliest

    def meal(self, label: str, earliest: int, minutes: int) -> None:
        r = pick_restaurant(self.prev, self.restaurants, self.used)
        if r is not None:
            self.used.add(r.get("content_id") or r.get("title"))
            self.move_to(r, earliest)
        elif self.t < earliest:
            if earliest - self.t >= MIN_FREE_GAP:
                self.events.append({"kind": "free", "start": hhmm(self.t), "end": hhmm(earliest), "text": "자유 시간 (주변 산책·카페 휴식)"})
            self.t = earliest
        self.events.append({"kind": "meal", "label": label, "start": hhmm(self.t), "end": hhmm(self.t + minutes), "place": r})
        self.t += minutes
        if r is not None:
            self.prev = r

    def _leave_base(self, to: dict, arrive_by: int | None = None) -> None:
        """숙소에서 첫 장소로 이동. arrive_by 가 있으면 그 시각에 맞춰 도착하도록 출발을 늦춘다."""
        est = estimate_travel(self.base, to)
        m = est["minutes"]
        if arrive_by is not None:
            self.t = max(6 * 60, arrive_by - m)
        self.events.append({"kind": "move", "start": hhmm(self.t), "end": hhmm(self.t + m), "from": self.base, "to": to, "text": est["text"]})
        self.t += m

    def visit(self, item: dict) -> None:
        p = item["place"]
        if self.prev is not None:
            self.move_to(p)
        elif self.base is not None and not self.events:
            self._leave_base(p)
        dur = stay_minutes(p)
        self.events.append({"kind": "visit", "start": hhmm(self.t), "end": hhmm(self.t + dur), "place": p, "note": item.get("note", "")})
        self.t += dur
        self.prev = p

    # ── 점심 ──
    def needs_lunch_before(self, item: dict) -> bool:
        """지금 점심을 먹지 않으면 이 장소가 끝나는 시각이 13:30을 넘어가는 경우, 먼저 점심"""
        if self.lunch_done or self.prev is None:
            return False
        p = item["place"]
        m_next = estimate_travel(self.prev, p)["minutes"]
        return self.t >= 11 * 60 + 30 or self.t + m_next + stay_minutes(p) > 13 * 60 + 30

    # ── 시간이 정해진 장소 ──
    def fits_before(self, item: dict, anchor: dict) -> bool:
        """이 장소를 (필요하면 점심도 먹고) 방문하고 정해진 장소로 이동해도 시작 시각 전에 끝나는가"""
        p, a = item["place"], anchor["place"]
        t0 = self.t
        if self.needs_lunch_before(item):
            t0 = max(t0, LUNCH_EARLIEST) + LUNCH_MIN + 10
        m1 = estimate_travel(self.prev, p)["minutes"] if self.prev is not None else 0
        return t0 + m1 + stay_minutes(p) + estimate_travel(p, a)["minutes"] <= anchor["fixed"][0]

    def anchor(self, anchor: dict) -> None:
        a, (s, e) = anchor["place"], anchor["fixed"]
        if self.prev is None and not self.events:
            self.t = s  # 하루의 첫 일정이 정해진 장소면 그 시각에 맞춰 하루를 시작한다 (앞에 빈 시간을 두지 않는다)
            if self.base is not None:
                self._leave_base(a, arrive_by=s)  # 숙소에서 그 시각에 맞춰 출발
        else:
            self._meals_before(s)
            self.move_to(a, s)
        start = max(self.t, s)
        end = max(e, start + 30)
        self.events.append({"kind": "visit", "start": hhmm(start), "end": hhmm(end), "place": a, "note": anchor.get("note", ""), "fixed": True})
        self.t, self.prev = end, a
        # 정해진 장소가 식사 시간대를 차지하면 그 식사는 거기서 해결한다 (축제 먹거리 등)
        covers_meal = a.get("meal") or str(a.get("content_type_id")) == "15"  # 식당·축제만 끼니를 대신한다 (카페·명소는 아님)
        if covers_meal and min(end, 13 * 60 + 30) - max(start, LUNCH_EARLIEST) >= 60:
            self.lunch_done = True
        if covers_meal and min(end, 20 * 60) - max(start, DINNER_EARLIEST) >= 90:
            self.dinner_done = True
        if a.get("meal"):  # 사용자가 말한 식당이면 식사 시간대에 걸치는 것만으로 그 끼니를 먹은 것으로 본다
            if start < 13 * 60 + 30 and end > 11 * 60 + 30:
                self.lunch_done = True
            if start < 20 * 60 + 30 and end > 17 * 60 + 30:
                self.dinner_done = True

    def _meals_before(self, anchor_start: int) -> None:
        """정해진 시각 전에 끝낼 수 있는 식사를 먼저 넣는다 (저녁 7시 공연이면 5시 반쯤 저녁)."""
        if self.prev is None:
            return
        if not self.lunch_done and anchor_start >= 14 * 60 and self.t < 13 * 60 + 30:
            self.meal("점심", LUNCH_EARLIEST, LUNCH_MIN)
            self.lunch_done = True
        if not self.dinner_done and anchor_start >= 18 * 60 + 30:
            start = anchor_start - DINNER_MIN - 25  # 식당에서 장소까지 이동할 시간을 남긴다
            if start >= 16 * 60 + 30 and max(self.t, start) + DINNER_MIN + 25 <= anchor_start:
                self.meal("저녁", max(start, self.t), DINNER_MIN)
                self.dinner_done = True

    def finish(self) -> None:
        if not self.lunch_done and self.prev is not None and self.t < 15 * 60:
            self.meal("점심", LUNCH_EARLIEST, LUNCH_MIN)
        if self.prev is not None and not self.dinner_done and self.t < 20 * 60:
            self.meal("저녁", DINNER_EARLIEST, DINNER_MIN)
        if self.base is not None and self.prev is not None and self.prev is not self.base:
            est = estimate_travel(self.prev, self.base)  # 숙소로 복귀
            self.events.append({"kind": "move", "start": hhmm(self.t), "end": hhmm(self.t + est["minutes"]),
                                "from": self.prev, "to": self.base, "text": est["text"]})
            self.t += est["minutes"]


def build_timeline(day_items: list[dict], restaurants: list[dict], used_restaurants: set[str],
                   base: dict | None = None) -> list[dict]:
    """
    Args:
        day_items: [{"place": place_dict, "note": str, "fixed": (시작 분, 끝 분) — 시간이 정해진 장소만}, ...]
                   그날 방문할 장소 (순서는 여기서 가까운 순으로 다시 정렬)
        restaurants: 취향 유사도 순으로 정렬된 음식점
        used_restaurants: 다른 날에 이미 쓴 음식점 (여기에 이번에 쓴 것도 추가됨)
        base: 숙소. 있으면 하루가 숙소에서 가장 가까운 장소부터 시작해 숙소로 돌아오는 동선이 된다.
    Returns:
        이벤트 리스트. kind = visit | move | meal | free   (시간이 정해진 장소의 visit 에는 fixed=True)
    """
    day = _Day(restaurants, used_restaurants, base)
    anchors = sorted((it for it in day_items if it.get("fixed")), key=lambda it: it["fixed"][0])
    free = [it for it in day_items if not it.get("fixed")]
    queue = order_from(base, free) if base is not None else order_by_proximity(free)

    while queue or anchors:
        nxt = anchors[0] if anchors else None
        item = queue[0] if queue else None
        if item is not None and (nxt is None or day.fits_before(item, nxt)):
            queue.pop(0)
            if nxt is None and any(it.get("fixed") for it in day_items):
                # 정해진 장소가 모두 지난 뒤: 너무 늦게 시작하는 장소는 뺀다
                m = estimate_travel(day.prev, item["place"])["minutes"] if day.prev is not None else 0
                if day.t + m >= LATEST_FREE_VISIT:
                    continue
            if day.needs_lunch_before(item):
                day.meal("점심", LUNCH_EARLIEST, LUNCH_MIN)
                day.lunch_done = True
            day.visit(item)
        else:
            day.anchor(anchors.pop(0))
    day.finish()
    return day.events
