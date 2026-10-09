"""
여러 지역 일정 요청 해석.  예) "대구 1박2일, 부산 2박3일 짜줘"

지역마다 기간이 따로 있는 요청이면 지역별로 독립된 일정을 만들 수 있게 [{"sido","area","nights"}, ...]로 나눕니다.
각 기간 표현 앞쪽 문장에서 지역을 찾고(대구 1박2일), 없으면 뒤쪽에서 찾습니다(1박2일 대구).
"""
import re

DURATION_RE = re.compile(r"(\d{1,2})\s*박(?:\s*(\d{1,2})\s*일)?|당일치기|(\d{1,2})\s*일\s*(?:간|동안|일정|여행|코스)")


def _nights(m: re.Match) -> int:
    if m.group(1):
        return int(m.group(1))
    if m.group(3):
        return max(int(m.group(3)) - 1, 0)
    return 0  # 당일치기


def parse_multi_trips(text: str, region_in) -> list[dict] | None:
    """
    region_in(문장) → (시도, 세부지역) | None : 문장에 나온 마지막 지역.
    기간 표현이 2개 이상이고 각각 지역이 있으며 서로 다른 지역이면 지역별 여행 리스트, 아니면 None.
    """
    durs = list(DURATION_RE.finditer(text or ""))
    if len(durs) < 2:
        return None

    def build(segments: list[str]) -> list[dict] | None:
        trips = []
        for seg, m in zip(segments, durs):
            reg = region_in(seg)
            if reg is None:
                return None
            trips.append({"sido": reg[0], "area": reg[1], "nights": _nights(m)})
        return trips

    before, prev = [], 0
    for m in durs:
        before.append(text[prev:m.end()])      # "대구 1박2일"
        prev = m.end()
    after = [text[m.end():(durs[i + 1].start() if i + 1 < len(durs) else len(text))] for i, m in enumerate(durs)]  # "1박2일 대구,"
    trips = build(before) or build(after)
    if not trips or len({(t["sido"], t["area"]) for t in trips}) < 2:
        return None  # 같은 지역을 여러 번 말한 것은 다중 지역이 아님
    return trips
