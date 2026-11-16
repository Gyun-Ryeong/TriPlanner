"""
회원 취향 기억 (백엔드가 '내 여행'에 저장한 장소로 만든 요약을 /chat 요청에 같이 보낸다).

profile = {"categories": {"문화시설": 12, "음식점": 8, ...}, "place_names": [...], "visited_ids": [...], "regions": [...]}

- 이번 대화에서 취향을 말하지 않았을 때만, 지난 여행에서 자주 담은 종류(박물관·카페 등)를 장소 고르기에 반영한다
- 저장했던 장소(이미 다녀왔거나 가려던 곳)는 순위를 뒤로 미뤄 새로운 곳을 먼저 보여준다
- 사용자가 이번에 말한 취향이 항상 우선이다
"""
from collections import Counter

# 장소 유형 → 취향 단어 (관광지·음식점·숙박처럼 누구나 담는 유형은 취향으로 보지 않는다)
_CATEGORY_WORDS = {"문화시설": "박물관 미술관", "레포츠": "레포츠 액티비티", "쇼핑": "쇼핑"}
# 장소 이름에 자주 나오면 취향으로 보는 말
_NAME_WORDS = ("카페", "박물관", "미술관", "갤러리", "해수욕장", "해변", "시장", "전망대", "공원", "수목원", "사찰", "계곡",
               "휴양림", "캠핑", "한옥", "체험", "테마파크", "온천", "섬", "폭포", "야경", "전시", "목장", "동물원", "아쿠아리움")
MIN_PLACES = 5      # 저장한 장소가 이보다 적으면 취향을 짐작하지 않는다
MIN_SHARE = 0.3     # 유형이 전체의 이 비율 이상일 때만 취향으로 본다
MAX_WORDS = 3


def taste_words(profile: dict | None) -> list[str]:
    """지난 여행 취향 단어. 예: ['박물관', '카페']. 근거가 부족하면 []."""
    if not profile:
        return []
    cats = {str(k): int(v) for k, v in (profile.get("categories") or {}).items() if isinstance(v, (int, float))}
    names = [str(n) for n in (profile.get("place_names") or [])]
    total = sum(cats.values())
    if total < MIN_PLACES and len(names) < MIN_PLACES:
        return []
    words: list[str] = []
    counts = Counter(w for n in names for w in _NAME_WORDS if w in n)
    words += [w for w, c in counts.most_common() if c >= 2]
    for cat, c in sorted(cats.items(), key=lambda kv: -kv[1]):
        if cat in _CATEGORY_WORDS and total and c / total >= MIN_SHARE and c >= 3:
            words += _CATEGORY_WORDS[cat].split()
    return list(dict.fromkeys(words))[:MAX_WORDS]


def visited_ids(profile: dict | None) -> set[str]:
    return {str(x) for x in ((profile or {}).get("visited_ids") or []) if x}


def push_visited_back(places: list[dict], profile: dict | None) -> list[dict]:
    """저장했던 장소는 순서를 유지한 채 뒤로 (새로운 곳을 먼저)"""
    seen = visited_ids(profile)
    if not seen:
        return places
    return [p for p in places if str(p.get("content_id")) not in seen] + [p for p in places if str(p.get("content_id")) in seen]
