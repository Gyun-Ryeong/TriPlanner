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


_STAY_KEY_RE = re.compile(r"(체크\s*인|체크\s*아웃|입실|퇴실)(?:\s*시간)?")
_AFTER_GAP_RE = re.compile(r"^[\s은는이가을를:=\-~]*$")      # "체크인은 오후 3시" 처럼 키워드와 시각 사이에 올 수 있는 말
_STAY_FILLER = {"부터", "까지", "쯤", "경", "정도", "이고", "이며", "인데", "고", "야", "이야", "이에요", "예요", "에요", "입니다", "하고", "하고요", "하며",
                "다음날", "이후", "이후로", "이전", "이전에", "로", "으로", "요", "그리고", "그리고요", "근데", "그런데", "해줘", "할게", "할게요", "해요", "에", "은", "는", "이"}
_BEFORE_GAP_RE = re.compile(r"^\s*(?:쯤|경|정도)?\s*(?:에|부터|까지|이후|전)?\s*(?:에는|엔)?\s*$")   # "3시쯤에 체크인"


def _stay_minutes_of(m: re.Match, is_out: bool) -> int | None:
    mer, h = m.group(1), int(m.group(2))
    minute = int(m.group(3) or m.group(5) or (30 if m.group(4) else 0))
    if h > 24 or minute > 59:
        return None
    if is_out and mer is None and h <= 8:
        return h * 60 + minute        # 체크아웃을 저녁 8시 이전 '오후'로 말하는 일은 없다 ("체크아웃 8시" = 오전)
    return _hour24(h, mer) * 60 + minute


def parse_stay_times(text: str) -> tuple[dict, str]:
    """
    "체크인은 오후 3시, 체크아웃 11시" → ({"in": 900, "out": 660}, 그 표현을 지운 나머지 말).
    시각을 같이 말하지 않은 체크인/체크아웃은 무시한다 (나머지 말에 그대로 남는다).
    """
    text = text or ""
    keys = list(_STAY_KEY_RE.finditer(text))
    found: dict[str, int] = {}
    cuts: list[tuple[int, int]] = []
    floor = 0   # 앞 표현이 쓴 자리까지
    for i, k in enumerate(keys):
        is_out = "아웃" in k.group(1) or "퇴" in k.group(1)
        nxt = keys[i + 1].start() if i + 1 < len(keys) else len(text)
        after = text[k.end():nxt]
        hit = _TIME_RE.search(after)
        span = None
        if hit and _AFTER_GAP_RE.match(after[:hit.start()]):
            span = (k.start(), k.end() + hit.end())
            val = _stay_minutes_of(hit, is_out)
        else:
            val = None
        if span is None:
            before = text[floor:k.start()]
            last = None
            for last in _TIME_RE.finditer(before):
                pass
            if last is not None and _BEFORE_GAP_RE.match(before[last.end():]):
                span = (floor + last.start(), k.end())
                val = _stay_minutes_of(last, is_out)
        if span is None or val is None:
            continue
        found["out" if is_out else "in"] = val
        cuts.append(span)
        floor = span[1]
    if not cuts:
        return {}, text
    out, pos = [], 0
    for a, b in sorted(cuts):
        out.append(text[pos:a])
        pos = b
    out.append(text[pos:])
    rest = " ".join(out)
    toks = [t for t in rest.split() if t.strip(",.") not in _STAY_FILLER]   # 시각을 지운 자리에 남은 조사·어미 조각
    rest = re.sub(r"\s*[,，]\s*(?:[,，]\s*)*", ", ", " ".join(toks))
    rest = re.sub(r"\s+", " ", rest).strip(" ,.")
    return found, rest
