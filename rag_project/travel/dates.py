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


# 날짜가 정해진 기념일 → "M월 D일" ('크리스마스 분위기', '크리스마스 마켓'처럼 날짜가 아닌 말은 건드리지 않는다)
_HOLIDAYS = [(r"크리스마스\s*이브", 12, 24), (r"크리스마스|성탄절|성탄", 12, 25), (r"신정|새해\s*첫\s*날", 1, 1),
             (r"삼일절", 3, 1), (r"어린이날", 5, 5), (r"현충일", 6, 6), (r"광복절", 8, 15), (r"개천절", 10, 3), (r"한글날", 10, 9)]
_HOLIDAY_TAIL = r"(?!\s*(?:분위기|느낌|마켓|트리|선물|노래|같|처럼|테마|장식|용품|카드|케이크|시즌|감성))"
_PART_OF_MONTH = {"초": 1, "상순": 1, "중순": 11, "하순": 21, "말": 25}  # "12월 초" → 12월 1일 (대략, 답변에 날짜를 보여줘서 고칠 수 있다)


def _month_after(today: date, n: int) -> int:
    return (today.month - 1 + n) % 12 + 1


def normalize_casual(text: str, today: date) -> str:
    """
    줄임말·대충 쓴 날짜를 파서가 아는 표현으로 바꾼다.
    낼 → 내일, 담주 → 다음주, 금욜 → 금요일, 담달 5일 → 12월 5일, 12월 초 → 12월 1일, 크리스마스 → 12월 25일
    """
    t = text or ""
    t = re.sub(r"낼\s*모레", "내일모레", t)
    t = re.sub(r"(?<![가-힣])낼(?=부터|에|\s|$|출발|떠나|가)", "내일", t)
    t = re.sub(r"(?<![가-힣])(?:지난|저번)\s*(?:지난|저번)\s*주|저저번\s*주", "저저번주", t)
    t = re.sub(r"(?<![가-힣])(?:지난|저번)\s*주", "저번주", t)
    t = re.sub(r"(?<![가-힣])(?:지난|저번)\s*달", "저번달", t)
    t = re.sub(r"다음\s*다음\s*주|다담\s*주", "다다음주", t)
    t = re.sub(r"다음\s*다음\s*달|다담\s*달", "다다음달", t)
    t = re.sub(r"(?<![가-힣])담\s*주", "다음주", t)
    t = re.sub(r"(?<![가-힣])(?:담|다음)\s*달", "다음달", t)
    t = re.sub(r"(?<![가-힣])이번\s*달", "이번달", t)
    t = re.sub(r"([월화수목금토일])욜", r"\1요일", t)
    for pat, m, d in _HOLIDAYS:
        t = re.sub(f"(?:{pat}){_HOLIDAY_TAIL}", f"{m}월 {d}일", t)
    month_of = {"이번달": today.month, "다음달": _month_after(today, 1), "다다음달": _month_after(today, 2)}
    last_m = _month_after(today, -1)
    last_y = today.year - (1 if last_m > today.month else 0)
    t = re.sub(r"저번달\s*(\d{1,2})\s*일", lambda m: f"{last_y}년 {last_m}월 {m.group(1)}일", t)
    t = re.sub(r"(다다음달|이번달|다음달)\s*(\d{1,2})\s*일", lambda m: f"{month_of[m.group(1)]}월 {m.group(2)}일", t)
    t = re.sub(r"(다다음달|이번달|다음달|\d{1,2}\s*월)\s*(초|상순|중순|하순|말)(?!일)",
               lambda m: f"{month_of.get(m.group(1)) or int(re.sub(r'\D', '', m.group(1)))}월 {_PART_OF_MONTH[m.group(2)]}일", t)
    return t


_WEEK_OFS = {"저저번": -14, "저번": -7, "이번": 0, "다음": 7, "담": 7, "다다음": 14}


def week_monday(today: date, word: str) -> date:
    """'저저번'/'저번'/'이번'/'다음'/'다다음' 주의 월요일"""
    return today - timedelta(days=today.weekday()) + timedelta(days=_WEEK_OFS.get(word, 0))


def date_in_month(month: int, day: int, today: date) -> date | None:
    """'12월' 다음에 '5일'이라고 답한 경우: 그 달의 그날 (지났으면 내년)"""
    return _make_date(None, month, day, today)


def day_of_month(day: int, today: date) -> date | None:
    """'20일'처럼 날만 말했을 때: 이번 달 그날 (이미 지났으면 다음 달)"""
    for n in (0, 1):
        m = _month_after(today, n)
        y = today.year + (1 if m < today.month else 0)
        try:
            d = date(y, m, day)
        except ValueError:
            continue
        if d >= today:
            return d
    return None


def parse_trip_dates(text: str, today: date) -> dict:
    """
    Returns:
        {"start": date|None, "end": date|None, "nights": int|None, "rest": str, "end_implied": bool, "bare_day": int|None}
        - start만 알 수 있으면 end는 None (몇 박인지 모름)
        - '2박 3일'처럼 기간만 말하면 start는 None, nights만 채워짐
        - bare_day: '포항 3일'처럼 'N일'만 있을 때 N (기간으로 넣고, 기간을 이미 알면 부르는 쪽이 날짜로 쓴다)
    """
    orig = normalize_casual(text or "", today)
    work = orig
    anchors: list[tuple[int, int, date, date | None, bool]] = []  # (시작위치, 끝위치, 시작일, 종료일, 종료일을 짐작했는지)

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
                anchors.append((m.start(), end_pos, res[1], res[2], len(res) > 3 and res[3]))
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

    # 2-1) 달 없이 날만: "20일부터", "20일에 출발", "25일 출발" → 이번 달(지났으면 다음 달)
    def h_day_only(m):
        s = day_of_month(int(m.group(1)), today)
        if not s:
            return None
        tail = re.match(r"\s*(?:부터|~|-)\s*(\d{1,2})\s*일(?:\s*까지)?", work[m.end():])  # "20일부터 22일까지"
        if tail:
            return m.end() + tail.end(), s, _end_from(s, None, int(tail.group(1)))
        return m.end(), s, None

    scan(re.compile(r"(?<![\d월/.~\-])(\d{1,2})\s*일\s*(?=부터|에\s*출발|에\s*떠나|에\s*가|출발)"), h_day_only)

    # 3) 다음/이번 주 X요일
    def h_week_wd(m):
        return m.end(), week_monday(today, m.group(1)) + timedelta(days=WD.index(m.group(2))), None

    scan(re.compile(r"(저저번|저번|다다음|다음|이번|담)\s*주\s*([월화수목금토일])\s*요일"), h_week_wd)

    # 3-1) 요일 범위·묶음: "월~금", "금부터 일까지", "다음주 월-금", "토일", "월 화 수 목 금", "토,일", "금 출발"
    def wd_start(prefix, idx):
        if prefix:
            return week_monday(today, prefix) + timedelta(days=idx)
        return _next_wd(today, idx)

    def h_wd_range(m):
        a, b = WD.index(m.group(2)), WD.index(m.group(3))
        s = wd_start(m.group(1), a)
        return m.end(), s, s + timedelta(days=(b - a) % 7)

    def h_wd_run(m):
        idx = [WD.index(ch) for ch in re.sub(r"[\s,·]", "", m.group(2))]
        steps = [(b - a) % 7 for a, b in zip(idx, idx[1:])]
        if any(st != 1 for st in steps) or (len(idx) == 2 and idx[1] < idx[0]):
            return None  # 이어진 요일만. 두 글자는 넘어가지 않게 ('일월저수지'의 '일월'은 요일이 아님, '금토일월'은 됨)
        s = wd_start(m.group(1), idx[0])
        return m.end(), s, s + timedelta(days=len(idx) - 1)

    def h_wd_one(m):
        return m.end(), wd_start(m.group(1), WD.index(m.group(2))), None

    _PRE = r"(?:(저저번|저번|다다음|다음|이번)\s*주\s*)?(?<![가-힣\d])"
    _ONE = r"[월화수목금토일]"
    scan(re.compile(_PRE + rf"({_ONE})(?:요일)?\s*(?:~|-|부터)\s*({_ONE})(?:요일)?(?:\s*까지)?(?![가-힣])"), h_wd_range)
    scan(re.compile(_PRE + rf"({_ONE}(?:\s*[,·]?\s*{_ONE}){{1,6}})(?![가-힣])"), h_wd_run)
    scan(re.compile(_PRE + rf"({_ONE})(?=\s*(?:출발|부터|에\s*출발|에\s*떠나))"), h_wd_one)

    # 4) 주말
    # '주말'은 토~일로 짐작한 것이라, '4박 5일'처럼 기간을 말하면 기간이 우선한다 (end_implied)
    def h_next_weekend(m):
        s, e = _weekend(today, True)
        return m.end(), s, e, True

    def h_weekend(m):
        s, e = _weekend(today, False)
        return m.end(), s, e, True

    def h_weekend_after_next(m):
        s, e = _weekend(today, True)
        return m.end(), s + timedelta(days=7), e + timedelta(days=7), True

    def h_past_weekend(m):
        sat = week_monday(today, m.group(1)) + timedelta(days=5)
        return m.end(), sat, sat + timedelta(days=1), True

    scan(re.compile(r"(저저번|저번)\s*주\s*(?:주)?\s*말"), h_past_weekend)
    scan(re.compile(r"다다음\s*주\s*(?:주)?\s*말"), h_weekend_after_next)
    scan(re.compile(r"(?:다음|담)\s*주\s*(?:주)?\s*말|(?:다음|담)\s*주말"), h_next_weekend)
    scan(re.compile(r"(?:이번\s*)?주\s*말"), h_weekend)

    # 5) 내일모레 / 오늘·내일·모레·글피
    scan(re.compile(r"내일\s*모레"), lambda m: (m.end(), today + timedelta(days=2), None))
    scan(re.compile(r"오늘\s*내일"), lambda m: (m.end(), today, today + timedelta(days=1)))  # "오늘내일" = 오늘~내일
    # 지난 날: 일정은 앞으로만 짜므로 부르는 쪽이 '이미 지났어요'라고 답한다
    for word, delta in (("엊그저께", -3), ("엊그제", -3), ("그저께", -2), ("그제", -2), ("어제", -1),
                        ("오늘", 0), ("내일", 1), ("모레", 2), ("글피", 3)):
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
    end_implied = False
    if valid:
        _, _, start, end, end_implied = max(valid, key=lambda a: a[0])

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
    elif m := re.search(r"(?<![\d.])(\d{1,2})\s*주(?:일)?(?=\s*(?:간|동안|일정|여행|코스|짜|$|\s))", orig):
        nights = int(m.group(1)) * 7 - 1  # "2주 일정" = 14일 ("다음 주", "이번 주"는 숫자가 없어 해당 없음)
    elif re.search(r"일주일|한\s*주\s*(?:간|동안|일정|여행)", orig):
        nights = 6
    elif re.search(r"한\s*달", orig):
        nights = 29  # 한 달 = 30일 (최대 기간)
    elif m := re.search(r"(이틀|사흘|나흘|닷새|엿새|이레|열흘|보름)", orig):
        nights = {"이틀": 1, "사흘": 2, "나흘": 3, "닷새": 4, "엿새": 5, "이레": 6, "열흘": 9, "보름": 14}[m.group(1)]

    # '포항 3일'처럼 날짜로 쓰이지 않은 'N일' (날짜 표현은 work에서 이미 지워졌다)
    bare_day = None
    plain = re.sub(r"\d{1,2}\s*박\s*\d{1,2}\s*일|\d{1,2}\s*일\s*(?:간|동안|일정|여행|코스)|부터\s*\d{1,2}\s*일", " ", work)
    bm = re.search(r"(?<![\d월/.~\-])(\d{1,2})\s*일(?!\s*(?:부터|에|까지|차|째|날|출발|~|-|요일))", plain)
    if bm and 2 <= int(bm.group(1)) <= 31 and not start:
        bare_day = int(bm.group(1))
        if nights is None and bare_day <= 30:
            nights = bare_day - 1

    if end_implied and nights is not None:
        end = start + timedelta(days=nights)  # "이번 주말 4박 5일" = 토요일부터 4박
    # rest: 날짜 표현을 지운 나머지 문장, end_implied: end를 '주말(토~일)'로 짐작했는지 (기간을 따로 알면 기간이 우선)
    # rough: 날짜 없이 '다음달', '12월', '다다음주'처럼 달·주만 말한 경우 (부르는 쪽이 며칠·무슨 요일인지 되묻는다)
    rough = None
    if not start:
        if re.search(r"(저저번|저번)\s*주|저번달", work):
            rough = {"past": True}
        elif wm := re.search(r"(다다음|다음|이번)\s*주(?!\s*말)", work):
            rough = {"week": week_monday(today, wm.group(1)).isoformat()}
        elif mm := re.search(r"(다다음달|다음달|이번달)|(?<!\d)(\d{1,2})\s*월(?!\s*\d)", work):
            month_of = {"이번달": today.month, "다음달": _month_after(today, 1), "다다음달": _month_after(today, 2)}
            month = month_of[mm.group(1)] if mm.group(1) else int(mm.group(2))
            if 1 <= month <= 12:
                rough = {"month": month}
    return {"start": start, "end": end, "nights": nights, "rest": work, "end_implied": end_implied and nights is None,
            "bare_day": bare_day, "rough": rough}
