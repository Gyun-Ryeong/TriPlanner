"""
시도 단위 지역 정보.
- ldong   : TourAPI 지역 필터용 법정동 시도 코드 (lDongRegnCd)
- city    : 날씨 예보 격자 기준 대표 도시 (collectors/weather.py의 REGION_GRID와 대응)
- aliases : 사용자가 입력할 수 있는 다른 표기
"""
import re

SIDO = {
    "서울": {"ldong": "11", "city": "서울", "aliases": ["서울특별시", "서울시"]},
    "부산": {"ldong": "26", "city": "부산", "aliases": ["부산광역시", "부산시"]},
    "대구": {"ldong": "27", "city": "대구", "aliases": ["대구광역시", "대구시"]},
    "인천": {"ldong": "28", "city": "인천", "aliases": ["인천광역시", "인천시"]},
    "광주": {"ldong": "29", "city": "광주", "aliases": ["광주광역시"]},
    "대전": {"ldong": "30", "city": "대전", "aliases": ["대전광역시", "대전시"]},
    "울산": {"ldong": "31", "city": "울산", "aliases": ["울산광역시", "울산시"]},
    "세종": {"ldong": "36", "city": "세종", "aliases": ["세종특별자치시", "세종시"]},
    "경기": {"ldong": "41", "city": "수원", "aliases": ["경기도"]},
    "강원": {"ldong": "51", "city": "강릉", "aliases": ["강원도", "강원특별자치도"]},
    "충북": {"ldong": "43", "city": "청주", "aliases": ["충청북도"]},
    "충남": {"ldong": "44", "city": "천안", "aliases": ["충청남도"]},
    "전북": {"ldong": "52", "city": "전주", "aliases": ["전라북도", "전북특별자치도"]},
    "전남": {"ldong": "46", "city": "여수", "aliases": ["전라남도"]},
    "경북": {"ldong": "47", "city": "경주", "aliases": ["경상북도"]},
    "경남": {"ldong": "48", "city": "창원", "aliases": ["경상남도"]},
    "제주": {"ldong": "50", "city": "제주", "aliases": ["제주도", "제주특별자치도"]},
}


def normalize_region(text: str) -> str | None:
    """'부산광역시', '제주도', '부산' 등을 표준 시도명('부산', '제주')으로 변환. 못 찾으면 None."""
    t = (text or "").strip()
    if not t:
        return None
    if t in SIDO:
        return t
    for name, info in SIDO.items():
        if t in info["aliases"]:
            return name
    # 문장 속에 포함된 경우 (예: "부산으로 갈래") - 긴 표기를 먼저 검사
    candidates = [(alias, name) for name, info in SIDO.items() for alias in info["aliases"]]
    candidates += [(name, name) for name in SIDO]
    for alias, name in sorted(candidates, key=lambda x: -len(x[0])):
        if alias in t:
            return name
    return None


# ── 구 TourAPI 시도 코드 (areaCode). 법정동 코드 조회가 실패했을 때 폴백으로만 사용 ──
LEGACY_AREA_CODE = {
    "서울": "1", "인천": "2", "대전": "3", "대구": "4", "광주": "5", "부산": "6", "울산": "7", "세종": "8",
    "경기": "31", "강원": "32", "충북": "33", "충남": "34", "경북": "35", "경남": "36",
    "전북": "37", "전남": "38", "제주": "39",
}

# ── 자주 말하는 시·군·명소 → 시도 ────────────────────────────────────
CITY_TO_SIDO = {
    # 제주
    "서귀포": "제주", "애월": "제주", "성산일출봉": "제주",
    # 부산
    "해운대": "부산", "광안리": "부산", "기장": "부산", "송정": "부산", "남포동": "부산", "감천": "부산",
    # 서울
    "강남": "서울", "홍대": "서울", "명동": "서울", "종로": "서울", "이태원": "서울", "성수": "서울", "잠실": "서울",
    # 경북
    "경주": "경북", "안동": "경북", "포항": "경북", "울릉도": "경북", "영주": "경북", "문경": "경북", "영덕": "경북",
    # 강원
    "강릉": "강원", "속초": "강원", "춘천": "강원", "양양": "강원", "평창": "강원", "동해": "강원", "삼척": "강원",
    # 전남
    "여수": "전남", "순천": "전남", "목포": "전남", "담양": "전남", "보성": "전남", "완도": "전남",
    # 전북
    "전주": "전북", "군산": "전북", "남원": "전북", "부안": "전북",
    # 경기
    "수원": "경기", "가평": "경기", "양평": "경기", "파주": "경기", "용인": "경기", "성남": "경기", "남양주": "경기",
    "분당": "경기", "판교": "경기", "광교": "경기", "일산": "경기", "동탄": "경기", "하남": "경기", "과천": "경기", "안양": "경기",
    # 경남
    "통영": "경남", "거제": "경남", "남해": "경남", "창원": "경남", "진주": "경남", "김해": "경남", "하동": "경남",
    # 충남
    "태안": "충남", "공주": "충남", "부여": "충남", "보령": "충남", "천안": "충남", "아산": "충남",
    # 충북
    "단양": "충북", "청주": "충북", "충주": "충북", "제천": "충북",
}

# 시군구가 아닌 동네 이름 → 그 동네가 속한 시 (시군구 단위로 장소를 받기 위해). 질문 문장에는 원래 이름이 남아 검색에 반영됩니다.
PARENT_AREA = {"판교": "성남", "광교": "수원", "일산": "고양", "동탄": "화성"}

_EXCLUDE_AFTER = re.compile(r"^\s*(?:은|는|이|가)?\s*(?:말고|빼고|제외|대신)")


def _mentions(text: str) -> list[tuple[int, int, str, str, bool]]:
    """텍스트에서 시도/도시 언급을 모두 찾습니다. (시작, 끝, 시도, 매칭어, 시도명 직접 언급 여부)"""
    found = []
    for name, info in SIDO.items():
        for tok in [name] + info["aliases"]:
            for m in re.finditer(re.escape(tok), text):
                found.append((m.start(), m.end(), name, tok, True))
    for city, sido in CITY_TO_SIDO.items():
        for m in re.finditer(re.escape(city), text):
            found.append((m.start(), m.end(), sido, city, False))
    # 같은 위치를 덮는 더 긴 매칭(예: '부산광역시' vs '부산')을 우선
    found.sort(key=lambda x: (x[0], -(x[1] - x[0])))
    kept, last_end = [], -1
    for f in found:
        if f[0] >= last_end:
            kept.append(f)
            last_end = f[1]
    return kept


def resolve_place(text: str) -> tuple[str | None, str]:
    """
    문장에서 (시도, 세부지역)을 찾습니다. '말고/대신' 앞에 나온 지역은 제외하고, 여러 곳이면 마지막 언급을 택합니다.
    예) '부산 해운대 가고 싶어' → ('부산', '해운대'),  '부산 말고 제주' → ('제주', ''),  '경주 갈래' → ('경북', '경주')
    """
    t = text or ""
    cands = [m for m in _mentions(t) if not _EXCLUDE_AFTER.match(t[m[1]:m[1] + 8])]
    if not cands:
        return None, ""
    sido = cands[-1][2]
    area = ""
    for _, _, s, tok, is_sido in cands:
        if s == sido and not is_sido:
            area = PARENT_AREA.get(tok, tok)
    return sido, area


def extract_region(text: str) -> str | None:
    return resolve_place(text)[0]


def mentioned_regions(text: str) -> list[tuple[str, str]]:
    """
    문장에 나온 지역을 등장 순서대로 (시도, 세부지역)으로 돌려줍니다. 같은 지역은 한 번만.
    '경기 성남'처럼 시도와 그 시의 도시를 함께 말하면 하나로 합치고, '말고/대신' 앞에 나온 지역은 제외합니다.
    예) '대구 1박2일, 부산 2박3일' → [('대구',''), ('부산','')]
    """
    t = text or ""
    found: list[tuple[str, str]] = []
    for start, end, sido, tok, is_sido in _mentions(t):
        if _EXCLUDE_AFTER.match(t[end:end + 8]):
            continue
        area = "" if is_sido else PARENT_AREA.get(tok, tok)
        merged = False
        for i, (s, a) in enumerate(found):
            if s == sido and (not a or not area or a == area):
                found[i] = (s, a or area)
                merged = True
                break
        if not merged:
            found.append((sido, area))
    return found
