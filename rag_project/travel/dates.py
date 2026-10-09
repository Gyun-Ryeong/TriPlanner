"""
한국어 날짜 표현 파서.

'내일', '이번 주말', '다음 주 금요일', '10월 10일부터 12일까지', '10/10~10/12', '2박 3일', '당일치기' 같은
표현을 날짜로 바꿉니다. 작은 로컬 LLM은 날짜 계산을 자주 틀려서, 날짜는 이 규칙 파서를 우선 사용합니다.
"""
import re
from datetime import date, timedelta

WD = "월화수목금토일"
_NEG = re.compile(r"\s*(?:은|는)?\s*(?:말고|빼고|대신|제외)")


def fmt_md(d: date) -> str:
    """10/10(토)"""
    return f"{d.month}/{d.day}({WD[d.weekday()]})"


def fmt_korean(d: date) -> str:
    """10월 10일(토)"""
    return f"{d.month}월 {d.day}일({WD[d.weekday()]})"


def parse_iso(s) -> date | None:
    try:
        return date.fromisoformat(str(s).strip()[:10])
    except (ValueError, TypeError):
        return None


def _mask(s: str, a: int, b: int) -> str:
    return s[:a] + " " * (b - a) + s[b:]


def _make_date(y, m, d, today: date) -> date | None:
    try:
        if y is None:
            cand = date(today.year, m, d)
            if cand < today:  # 이미 지난 월/일이면 내년으로 해석
                cand = date(today.year + 1, m, d)
            return cand
        return date(y, m, d)
    except ValueError:
        return None


def _weekend(today: date, nxt: bool) -> tuple[date, date]:
    if not nxt:
        wd = today.weekday()
        if wd == 5:
            return today, today + timedelta(days=1)
        if wd == 6:
            return today, today
        sat = today + timedelta(days=5 - wd)
        return sat, sat + timedelta(days=1)
    monday = today - timedelta(days=today.weekday()) + timedelta(days=7)
    sat = monday + timedelta(days=5)
    return sat, sat + timedelta(days=1)


def _next_wd(today: date, idx: int) -> date:
    return today + timedelta(days=(idx - today.weekday()) % 7)


def _end_from(s: date, month: int | None, day: int) -> date | None:
    """범위의 끝 날짜 계산. 월을 생략하면 시작과 같은 달(그 날이 이미 지났으면 다음 달)로 봅니다."""
    try:
        if month is not None:
            e = date(s.year, month, day)
            return e if e >= s else date(s.year + 1, month, day)
        e = date(s.year, s.month, day)
        if e >= s:
            return e
        return date(s.year + (1 if s.month == 12 else 0), 1 if s.month == 12 else s.month + 1, day)
    except ValueError:
        return None


def parse_trip_dates(text: str, today: date) -> dict:
    """
    Returns:
        {"start": date|None, "end": date|None, "nights": int|None, "rest": str}
        - start만 알 수 있으면 end는 None (몇 박인지 모름)
        - '2박 3일'처럼 기간만 말하면 start는 None, nights만 채워짐
    """
    orig = text or ""
    work = orig
    anchors: list[tuple[int, int, date, date | None]] = []  # (시작위치, 끝위치, 시작일, 종료일)

    def scan(pattern, handler):
        """패턴을 반복 검색하되, 한 번 처리한 구간은 지워서 다시 잡히지 않게 합니다."""
        nonlocal work
        while True:
            m = pattern.search(work)
            if not m:
                return
            res = handler(m)  # (끝위치, 시작일, 종료일) 또는 None
            end_pos = res[0] if res else m.end()
            if res and res[1] is not None:
                anchors.append((m.start(), end_pos, res[1], res[2]))
            work = _mask(work, m.start(), end_pos)

    # 1) M월 D일 [부터/~ [M월] D일]
    def h_md(m):
        y = int(m.group(1)) if m.group(1) else None
        s = _make_date(y, int(m.group(2)), int(m.group(3)), today)
        if s is None:
            return None
        tail = re.match(r"\s*(?:부터|~|-|–|—|에서)\s*(?:(\d{1,2})\s*월\s*)?(\d{1,2})\s*일(?:\s*까지)?", work[m.end():])
        if not tail:
            return m.end(), s, None
        em = int(tail.group(1)) if tail.group(1) else None
        return m.end() + tail.end(), s, _end_from(s, em, int(tail.group(2)))

    scan(re.compile(r"(?:(\d{4})\s*년\s*)?(\d{1,2})\s*월\s*(\d{1,2})\s*일"), h_md)

    # 2) M/D, M.D [~ M/D]
    def h_slash(m):
        s = _make_date(None, int(m.group(1)), int(m.group(2)), today)
        if s is None:
            return None
        tail = re.match(r"\s*(?:부터|~|-|–|—)\s*(\d{1,2})\s*[/.]\s*(\d{1,2})", work[m.end():])
        if not tail:
            return m.end(), s, None
        return m.end() + tail.end(), s, _end_from(s, int(tail.group(1)), int(tail.group(2)))

    scan(re.compile(r"(?<![\d.])(\d{1,2})\s*[/.]\s*(\d{1,2})(?![\d.])(?!\s*박)"), h_slash)

    # 3) 다음/이번 주 X요일
    def h_week_wd(m):
        monday = today - timedelta(days=today.weekday())
        if m.group(1) in ("다음", "담"):
            monday += timedelta(days=7)
        return m.end(), monday + timedelta(days=WD.index(m.group(2))), None

    scan(re.compile(r"(다음|이번|담)\s*주\s*([월화수목금토일])\s*요일"), h_week_wd)

    # 4) 주말
    def h_next_weekend(m):
        s, e = _weekend(today, True)
        return m.end(), s, e

    def h_weekend(m):
        s, e = _weekend(today, False)
        return m.end(), s, e

    scan(re.compile(r"(?:다음|담)\s*주\s*(?:주)?\s*말|(?:다음|담)\s*주말"), h_next_weekend)
    scan(re.compile(r"(?:이번\s*)?주\s*말"), h_weekend)

    # 5) 내일모레 / 오늘·내일·모레·글피
    scan(re.compile(r"내일\s*모레"), lambda m: (m.end(), today + timedelta(days=2), None))
    for word, delta in (("오늘", 0), ("내일", 1), ("모레", 2), ("글피", 3)):
        scan(re.compile(word), lambda m, d=delta: (m.end(), today + timedelta(days=d), None))

    # 6) X요일 (부터 Y요일)
    def h_wd(m):
        s = _next_wd(today, WD.index(m.group(1)))
        e = None
        if m.group(2):
            e = s + timedelta(days=(WD.index(m.group(2)) - WD.index(m.group(1))) % 7)
        return m.end(), s, e

    scan(re.compile(r"([월화수목금토일])\s*요일(?:\s*(?:부터|~|-)\s*([월화수목금토일])\s*요일)?"), h_wd)

    # 말고/대신 앞에 나온 날짜는 제외하고 마지막 언급을 사용
    valid = [a for a in anchors if not _NEG.match(orig[a[1]:a[1] + 8])]
    start = end = None
    if valid:
        _, _, start, end = max(valid, key=lambda a: a[0])

    # 기간 표현
    nights = None
    if m := re.search(r"(\d{1,2})\s*박(?:\s*(\d{1,2})\s*일)?", orig):
        nights = int(m.group(1))
    elif re.search(r"당일치기|당일\s*여행|당일로|당일", orig):
        nights = 0
    elif m := re.search(r"(\d{1,2})\s*일\s*(?:간|동안|일정|여행|코스)", orig):
        nights = max(int(m.group(1)) - 1, 0)
    elif m := re.search(r"부터\s*(\d{1,2})\s*일(?!\s*(?:까지|에))", orig):
        nights = max(int(m.group(1)) - 1, 0)  # "오늘부터 7일" = 7일 일정
    elif m := re.search(r"(이틀|사흘|나흘)", orig):
        nights = {"이틀": 1, "사흘": 2, "나흘": 3}[m.group(1)]

    return {"start": start, "end": end, "nights": nights, "rest": work}  # rest: 날짜 표현을 지운 나머지 문장
