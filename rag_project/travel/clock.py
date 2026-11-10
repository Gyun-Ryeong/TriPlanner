"""
사용자가 말한 시각 읽기: "저녁 7시부터 9시", "19:00~21:00", "오후 7시 30분", "7시 반".

축제 시간은 TourAPI에 없어서 사용자가 알려줘야 한다. 말한 시각을 '하루 중 몇 분째'(0~1440)로 바꿔준다.
"""
import re

_TIME_RE = re.compile(
    r"(?:(오전|아침|새벽|오후|낮|점심|저녁|밤)\s*)?(\d{1,2})\s*"
    r"(?:시(?!간)\s*(?:(\d{1,2})\s*분|(반))?|:(\d{2}))"
)


def _hour24(h: int, mer: str | None) -> int:
    if mer in ("오후", "저녁", "밤"):
        return h + 12 if h < 12 else (24 if (mer == "밤" and h == 12) else h)
    if mer in ("오전", "아침", "새벽"):
        return 0 if h == 12 else h
    if mer in ("낮", "점심"):
        return h + 12 if 1 <= h <= 5 else h
    return h + 12 if 1 <= h <= 8 else h  # 말머리가 없으면 1~8시는 오후로 본다 (축제·공연이 아침 8시 이전에 열리는 일은 드물다)


def strip_times(text: str) -> str:
    """말에서 시각 표현("저녁 7시부터 9시까지", "19:00~21:00")을 지운다. 장소 이름만 남길 때 쓴다."""
    out = _TIME_RE.sub(" ", text or "")
    out = re.sub(r"(?:부터|까지|에|쯤|경|정도)(?=\s|$)", " ", out)
    return re.sub(r"\s+", " ", out).strip()


def hhmm(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def parse_time_range(text: str) -> tuple[int, int | None] | None:
    """
    Returns: (시작 분, 끝 분 또는 None). 시각이 없으면 None.
    시작만 말하면 끝은 None (호출하는 쪽이 체류 시간으로 채운다). '시간'(3시간)은 시각이 아니다.
    """
    found = []
    for m in _TIME_RE.finditer(text or ""):
        mer, h = m.group(1), int(m.group(2))
        minute = int(m.group(3) or m.group(5) or (30 if m.group(4) else 0))
        if h > 24 or minute > 59:
            continue
        found.append((mer, h, minute))
    if not found:
        return None
    mer0, h0, m0 = found[0]
    start = _hour24(h0, mer0) * 60 + m0
    if start > 24 * 60:
        return None
    if len(found) < 2:
        return start, None
    mer1, h1, m1 = found[1]
    end = _hour24(h1, mer1 or mer0) * 60 + m1  # 끝에 말머리가 없으면 시작과 같은 말머리 ("저녁 7시부터 9시")
    if end <= start:
        end += 12 * 60 if (mer1 is None and end + 12 * 60 > start) else 0
    if end <= start or end > 24 * 60:
        return start, None
    return start, end
