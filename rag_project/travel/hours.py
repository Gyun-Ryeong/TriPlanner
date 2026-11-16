"""
영업시간·휴무일 반영.

TourAPI 상세정보(detailIntro2)의 휴무일 문구('매주 월요일', '매월 둘째·넷째 주 월요일', '설·추석 당일', '연중무휴')를 읽어
그날 문을 닫는 장소가 일정에 들어가지 않게 합니다. 운영시간('09:00~18:00')은 시간표에서 늦게 도착하는 곳을 알려줄 때 씁니다.

문구가 제각각이라 확실히 읽히는 것만 씁니다. 모르면 '연다'고 봅니다 (괜히 좋은 장소를 빼지 않게).
"""
import re
from datetime import date

WD = "월화수목금토일"

# detailIntro2는 같은 사실을 장소 유형마다 다른 필드 이름으로 준다 (운영시간, 휴무일)
_FIELDS = {
    "12": ("usetime", "restdate"),
    "14": ("usetimeculture", "restdateculture"),
    "28": ("usetimeleports", "restdateleports"),
    "38": ("opentime", "restdateshopping"),
    "39": ("opentimefood", "restdatefood"),
}

# 음력 명절 (설·추석 연휴 3일, 가운데가 당일). 해마다 날짜가 달라 표로 둔다
_LUNAR = {
    "설": {2026: (2, 17), 2027: (2, 7), 2028: (1, 27)},
    "추석": {2026: (9, 25), 2027: (9, 15), 2028: (10, 3)},
}
# '시설'·'설치'에 걸리지 않게: 설날, 구정, 또는 앞에 글자가 없는 '설' 뒤에 ·/연휴/당일 등
_LUNAR_RE = {"설": re.compile(r"설날|구정|(?<![가-힣])설(?=\s*(?:[·,/및]|연휴|당일|$))"), "추석": re.compile(r"추석")}
_NTH = {"첫": 1, "둘": 2, "셋": 3, "넷": 4, "다섯": 5}


def _intro_field(place: dict, which: int) -> str:
    intro = place.get("intro") or {}
    key = _FIELDS.get(str(place.get("content_type_id", "")), ("usetime", "restdate"))[which]
    return str(intro.get(key) or intro.get(("usetime", "restdate")[which]) or "").strip()


def rest_text(place: dict) -> str:
    return _intro_field(place, 1)


def hours_text(place: dict) -> str:
    return _intro_field(place, 0)


def _holiday_closed(text: str, d: date) -> bool:
    for name, by_year in _LUNAR.items():
        if not _LUNAR_RE[name].search(text):
            continue
        md = by_year.get(d.year)
        if not md:
            continue
        mid = date(d.year, *md)
        only_day = re.search(r"당일", text) and not re.search(r"연휴", text)
        if (d == mid) if only_day else (abs((d - mid).days) <= 1):
            return True
    return False


def closed_on(place: dict, d: date) -> bool:
    """그날 문을 닫는지. 휴무일 정보가 없거나 읽을 수 없으면 False."""
    text = rest_text(place)
    if not text or re.match(r"\s*(?:연중\s*무휴|없음|무휴|해당\s*없음)", text):
        return False
    if re.search(r"가능성|문의|전화", text) and not re.search(r"요일", text):
        return False
    if _holiday_closed(text, d):
        return True
    for m in re.finditer(r"(\d{1,2})\s*월\s*(\d{1,2})\s*일", text):  # 1월 1일 같은 날짜
        if (d.month, d.day) == (int(m.group(1)), int(m.group(2))):
            return True
    if re.search(r"신정|1/1", text) and (d.month, d.day) == (1, 1):
        return True
    days = {WD.index(w) for w in re.findall(r"([월화수목금토일])\s*요일", text)}
    # '월·화요일'처럼 요일을 이어 쓴 경우
    for run in re.findall(r"((?:[월화수목금토일]\s*[,·/]\s*)+[월화수목금토일])\s*요일", text):
        days |= {WD.index(w) for w in re.findall(r"[월화수목금토일]", run)}
    if d.weekday() not in days:
        return False
    nths = {_NTH[w] for w in re.findall(r"(첫|둘|셋|넷|다섯)\s*째", text)}
    last = bool(re.search(r"마지막\s*주", text))
    if not nths and not last:
        return True  # 매주 그 요일
    week = (d.day - 1) // 7 + 1
    is_last = (d.day + 7) > _month_days(d)
    return week in nths or (last and is_last)


def _month_days(d: date) -> int:
    nxt = date(d.year + (d.month == 12), d.month % 12 + 1, 1)
    return (nxt - date(d.year, d.month, 1)).days


def open_range(place: dict) -> tuple[int, int] | None:
    """운영시간 첫 구간 (여는 분, 닫는 분). 예: '09:00~18:00 (입장 마감 17:00)' → (540, 1080). 못 읽으면 None."""
    m = re.search(r"(\d{1,2})\s*[:시]\s*(\d{2})?\s*분?\s*[~\-–]\s*(\d{1,2})\s*[:시]\s*(\d{2})?", hours_text(place))
    if not m:
        return None
    o = int(m.group(1)) * 60 + int(m.group(2) or 0)
    c = int(m.group(3)) * 60 + int(m.group(4) or 0)
    if c <= o:
        c += 24 * 60  # 새벽까지 영업
    return (o, c) if 0 <= o < 24 * 60 else None
