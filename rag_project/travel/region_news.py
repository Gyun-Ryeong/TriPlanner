"""
여행지 소식 카드 (여행 일정 화면·알림 탭).

그 여행지의 '주의할 이슈'(통제·침수·사고·특보 등)와 '지역 소식'을 합쳐, 기사마다 사진을 붙여 돌려줍니다.
- 이슈: risk_scanner (네이버 + 연합뉴스). 화면에 그대로 보이므로 제목에 이슈 단어가 있고 정책·예방·해설 기사가 아닌 것만
- 소식: news.pick_broad (지역 이름이 있는 최근 기사, 같은 사건은 하나로)
- 사진: 기사 원문의 대표 사진(og:image). 없으면(연합뉴스처럼 링크가 없는 기사 포함) 그 지역 대표 관광지 사진
AI는 쓰지 않습니다.
"""
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from email.utils import parsedate_to_datetime

from collectors.og_image import og_image
from collectors.yonhap import attach_links
from travel import news
from travel.photos import _resolve, region_photo
from travel.risk_scanner import RISK_QUERIES, _POLICY_RE, scan_regional_risks

MAX_ISSUES = 3
MAX_TOTAL = 6  # 칸(사건사고 / 지역 소식)마다
BODY_MAX = 3000  # 화면 '본문 보기'에 싣는 최대 글자 수
INCIDENT_KIND = {"fire": "화재", "traffic": "교통사고", "crime": "사건"}
NEWS_QUERIES = ("", "여행", "관광", "축제")
# 여행자에게 쓸모 있는 소식이 먼저 보이게 (행정·경제 기사보다 앞에)
_TRAVEL_RE = re.compile(r"여행|관광|축제|명소|개장|개막|개최|공연|전시|체험|해수욕장|해변|야경|맛집|카페|행사|페스티벌|"
                        r"박물관|미술관|공원|등산|둘레길|케이블카|불꽃|조명|단풍|벚꽃|눈꽃|빛|마켓|투어|박람회|크리스마스|트리")


def _iso_date(pub: str) -> str:
    """'2026-11-23 16:06'(이슈) 또는 RFC 2822(뉴스) → '2026-11-23'"""
    if re.match(r"\d{4}-\d{2}-\d{2}", pub or ""):
        return pub[:10]
    try:
        return parsedate_to_datetime(pub).astimezone().strftime("%Y-%m-%d")
    except Exception:
        return ""


def is_travel_issue(title: str) -> bool:
    """화면에 '주의' 로 보여도 될 기사: 제목에 이슈 단어가 있고, 정책·예방·해설·이야기 기사가 아님"""
    check = title.replace("무사고", "")
    has_word = any(all(tok in check for tok in kw.split()) for kws in RISK_QUERIES.values() for kw in kws)
    return (has_word and not news.is_column(title) and not news._NOT_INCIDENT_RE.search(title)
            and not _POLICY_RE.search(title) and not news._FICTION_RE.search(title))


def region_news(name: str, region: str = "", limit: int = MAX_TOTAL) -> dict:
    """
    name: 도시·시군구 또는 시도 (예: 부산, 수원, 곡성)   region: 앱의 권역 이름 (예: '경상도') — 같은 이름 구별용
    limit: 칸(사건사고 / 지역 소식)마다 최대 장수
    Returns: {"label", "counts": {"incident", "local", "issue"},
              "items": [{"group": "incident"|"local", "kind": "issue"|"incident"|"news", "category", "title", "summary",
                         "link", "source", "date", "image", "image_is_fallback"}], "warnings"}
      group=incident: 여행에 영향을 주는 이슈(kind=issue, 통제·침수·특보) + 사건·사고(kind=incident, 화재·교통사고·사건)
      group=local   : 지역 소식 (여행 관련 먼저)
    """
    sido, area = _resolve(name, region)
    label = area or sido or ""
    if not label:
        return {"label": name, "items": [], "warnings": [f"'{name}' 지역을 찾지 못했어요"]}
    warnings: list[str] = []

    # 1) 주의할 이슈
    try:
        risks, w = scan_regional_risks(sido, area)
        warnings += w
    except Exception as e:
        risks, warnings = [], warnings + [f"이슈 조회 실패: {type(e).__name__}"]
    issues: list[dict] = []
    for r in risks:
        if is_travel_issue(r["title"]) and not any(news._similar(r["title"], i["title"], 0.3) for i in issues):
            issues.append(r)  # 같은 사건을 여러 언론이 쓴 건 하나로
        if len(issues) >= MAX_ISSUES:
            break

    # 2) 사건·사고 (챗봇의 '○○ 사건사고' 답변과 같은 기준: 네이버 + 연합뉴스, 지역·사건 단어가 제목에)
    safety_items, w = news.fetch([f"{label} {q}" for q in news.SAFETY_QUERIES], display=50)
    yonhap, yw = news.fetch_yonhap()
    warnings += w + yw
    incidents = news.pick_safety(yonhap + safety_items, label, n=limit)

    # 3) 지역 소식
    items, w = news.fetch([f"{label} {q}".strip() for q in NEWS_QUERIES], display=20)
    warnings += w
    broad = news.pick_broad(items, label, n=limit * 3)
    broad.sort(key=lambda it: bool(_TRAVEL_RE.search(it["title"])), reverse=True)  # 여행 관련 먼저 (그 안은 원래 순서)

    def card(kind: str, group: str, category: str, it: dict) -> dict:
        return {"kind": kind, "group": group, "category": category, "title": it["title"],
                "summary": news._snippet(it.get("description", ""), 120), "link": it.get("link", ""),
                "source": it.get("source") if it.get("source") not in (None, "", "naver_news") else "",
                "date": _iso_date(it.get("pub_date", "")),
                "_body": it.get("body") or it.get("description", "")}

    # 사건사고 칸: 여행에 영향을 주는 이슈(주의) 먼저, 그다음 사건·사고 (같은 사건은 하나로)
    incident_cards: list[dict] = [card("issue", "incident", r["category"], r) for r in issues]
    for it in incidents:
        if len(incident_cards) >= limit:
            break
        if not any(news._similar(it["title"], c["title"], 0.3) for c in incident_cards):
            incident_cards.append(card("incident", "incident", INCIDENT_KIND[news._incident_kind(it["title"])], it))

    # 지역 소식 칸: 사건사고 칸과 겹치는 기사는 빼고, 같은 소식은 하나로
    local_cards: list[dict] = []
    for it in broad:
        if len(local_cards) >= limit:
            break
        if (any(news._similar(it["title"], c["title"], 0.25) for c in local_cards + incident_cards)
                or news.SAFETY_ASK_RE.search(it["title"])):
            continue
        local_cards.append(card("news", "local", "", it))
    cards = incident_cards + local_cards

    # 링크가 없는 연합뉴스 기사: 네이버 검색으로 원문 주소를 찾는다 (찾으면 원문 보기 + 기사 사진).
    # 그래도 없으면 받은 본문을 실어 화면에서 '본문 보기'로 연다
    attach_links(cards, limit=len(cards))
    for c in cards:
        body = c.pop("_body")
        if not c["link"] and c["source"] == "연합뉴스":
            c["body"] = body[:BODY_MAX]
            c["credit"] = "연합뉴스 · 행정안전부 재난안전데이터 공유플랫폼"

    # 3) 사진: 원문 대표 사진을 동시에 찾고, 없으면 지역 대표 사진
    with ThreadPoolExecutor(max_workers=6) as ex:
        images = list(ex.map(lambda c: og_image(c["link"]), cards))
    fallback = ""
    if not all(images):
        try:
            fallback = region_photo(name, region).get("image", "")
        except Exception:
            fallback = ""
    for c, img in zip(cards, images):
        c["image"] = img or fallback
        c["image_is_fallback"] = not img
    return {"label": label, "items": cards, "warnings": warnings,
            "counts": {"incident": len(incident_cards), "local": len(local_cards),
                       "issue": sum(c["kind"] == "issue" for c in incident_cards)},
            "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M")}
