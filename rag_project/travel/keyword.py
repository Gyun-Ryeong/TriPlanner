"""
키워드 검색 + 벡터 검색 섞기 (하이브리드 검색).

임베딩 모델(MiniLM)은 '분위기'는 잘 잡지만 '국밥', '해수욕장' 같은 정확한 단어는 놓치곤 합니다.
그래서 질문에서 뽑은 단어가 장소 이름·분류·소개글에 들어 있는지로 키워드 순위를 따로 만들고,
벡터 순위와 RRF(Reciprocal Rank Fusion)로 합칩니다: 점수 = Σ 1 / (60 + 순위)
- 키워드가 하나도 안 맞는 장소는 벡터 순위 그대로 (키워드 순위 점수 없음)
- 주소는 비교하지 않는다 (같은 지역 장소는 모두 지역 이름을 갖고 있어 의미가 없다)
"""
import re

RRF_K = 60
KEYWORD_WEIGHT = 1.0  # 키워드 순위를 벡터 순위와 같은 무게로

# 조사·어미 (긴 것부터 떼어낸다)
_JOSA = sorted(["하기", "하러", "하면서", "으로", "에서", "까지", "부터", "이랑", "하고", "처럼", "같은", "위주", "위주로", "중심", "중심으로",
                "을", "를", "이", "가", "은", "는", "에", "로", "도", "만", "와", "과", "랑", "의"], key=len, reverse=True)
# 어디에나 붙는 말이라 키워드로 쓰지 않는다
_STOP = {"여행", "추천", "일정", "코스", "장소", "좋은", "좋아", "좋아요", "가고", "싶어", "싶어요", "싶은", "가볼", "가볼만한",
         "가볼만", "갈만한", "곳", "데", "곳들", "명소", "핫플", "맛집", "유명한", "인기", "많은", "있는", "하는", "할", "곳으로",
         "짜줘", "짜주세요", "해줘", "알려줘", "좀", "그리고", "또", "같이", "함께", "우리", "저희", "다시", "위주", "중심",
         "당일치기", "박", "일", "내일", "모레", "주말", "이번", "다음", "아이", "아이랑", "아이와", "가족", "가족과", "가족이랑",
         "부모님", "부모님과", "친구", "친구랑", "친구들", "친구들과", "연인", "혼자", "커플", "둘이", "조용한", "편하게", "천천히"}
_KEEP_END = ("마을", "가을", "겨울", "노을", "하늘", "바닷가", "강가", "물가", "냇가", "해변가", "놀이", "섬도")
_ONE_CHAR ={"산", "섬", "숲", "절", "강", "굴"}  # 한 글자라도 뜻이 분명한 말


def query_terms(query: str, region_words: tuple[str, ...] = ()) -> list[str]:
    """질문에서 키워드 뽑기. '대구 국밥 맛집 위주로' → ['국밥']"""
    out = []
    for w in re.findall(r"[가-힣A-Za-z0-9]+", query or ""):
        for j in _JOSA:
            if w.endswith(_KEEP_END) or w in _STOP:
                break  # 한옥마을의 '을', 바닷가의 '가'는 조사가 아니다
            if w.endswith(j) and len(w) - len(j) >= 1:
                w = w[: -len(j)]
                break
        if w in _STOP or re.search(r"\d", w):  # 2박·3일·10월 같은 날짜·기간
            continue
        if len(w) >= 3 and w.endswith("집"):
            w = w[:-1]  # 국밥집 → 국밥 (이름은 '○○국밥'인 경우가 많다)
        if len(w) < 2 and w not in _ONE_CHAR:
            continue
        if any(w in r or r in w for r in region_words if r):
            continue  # 지역 이름
        out.append(w)
    return list(dict.fromkeys(out))


def keyword_score(place: dict, terms: list[str], category: str = "", overview: str = "") -> float:
    """
    이름에 있으면 3, 분류에 2, 소개글에 1 (단어마다 더함).
    terms 항목은 단어 또는 (단어, 무게) — 합성어 뒷부분처럼 덜 확실한 단어는 무게를 낮춘다
    """
    title = place.get("title", "")
    score = 0.0
    for t in terms:
        t, weight = (t, 1.0) if isinstance(t, str) else t
        if t in title:
            score += 3 * weight
        elif t in category:
            score += 2 * weight
        elif t in overview:
            score += 1 * weight
    return score


def expand_rare(terms: list[str], texts: list[str], min_hits: int = 5) -> list:
    """
    통째로 맞는 장소가 min_hits곳도 안 되는 합성어는 뒤 2글자도 절반 무게로 찾는다.
    전통시장 → '시장'(부전시장), 녹차밭 → '차밭'(보성차밭). 해수욕장처럼 통째로 많이 맞으면 그대로 둔다.
    """
    out: list = list(terms)
    for t in terms:
        if len(t) >= 3 and t[-2:] not in _STOP and t[-2:] not in terms and sum(t in x for x in texts) < min_hits:
            out.append((t[-2:], 0.5))
    return out


def fuse(vector_order: list[str], keyword_scores: dict[str, float]) -> list[str]:
    """벡터 순위(id 목록)와 키워드 점수를 RRF로 합친 순위. 키워드 점수가 0이면 벡터 순위만 반영."""
    kw_rank = {k: r for r, k in enumerate(sorted((k for k, s in keyword_scores.items() if s > 0),
                                                 key=lambda k: -keyword_scores[k]))}
    score = {}
    for r, k in enumerate(vector_order):
        score[k] = 1 / (RRF_K + r) + (KEYWORD_WEIGHT / (RRF_K + kw_rank[k]) if k in kw_rank else 0.0)
    return sorted(vector_order, key=lambda k: -score[k])
