"""
지역 리스크 뉴스 스캐너 (네이버 뉴스 검색 기반)

날씨 특보, 행사 취소, 통제/휴장, 안전 사고 같은 '여행에 영향을 주는 이슈'를
지역 이름과 함께 검색해서 최근 기사만 추려냅니다.
"""
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

from collectors.naver_news import search_news

# 카테고리별 검색 키워드. "축제 취소"처럼 공백이 있으면 기사에 두 단어가 모두 있어야 통과.
RISK_QUERIES = {
    "기상": ["특보", "태풍", "호우", "폭설"],
    "행사": ["축제 취소", "행사 연기"],
    "통제·휴장": ["통제", "폐쇄", "휴장"],
    "안전": ["산불", "침수", "사고"],
}


def _parse_pub_date(s: str) -> datetime | None:
    try:
        dt = parsedate_to_datetime(s)
    except Exception:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def scan_regional_risks(
    region: str,
    area: str = "",
    days_back: int = 7,
    per_query: int = 10,
    max_items: int = 12,
) -> tuple[list[dict], list[str]]:
    """
    Args:
        region: 시도명 (예: "부산")
        area: 시군구/세부지역 (예: "해운대"). 있으면 이 이름으로 검색
        days_back: 최근 며칠 이내 기사만 사용
        per_query: 쿼리당 가져올 기사 수
        max_items: 최종 반환 개수 (최신순)

    Returns:
        (뉴스 리스트, 경고 메시지 리스트)
        뉴스 항목: {"id": "N1", "category", "keyword", "title", "description", "link", "pub_date"}
    """
    scope = area or region
    tasks = [(cat, kw) for cat, kws in RISK_QUERIES.items() for kw in kws]
    warnings: list[str] = []

    def run(task):
        cat, kw = task
        return cat, kw, search_news(f"{scope} {kw}", display=per_query, sort="date")

    raw, failures, last_err = [], 0, ""
    with ThreadPoolExecutor(max_workers=6) as ex:
        futures = [ex.submit(run, t) for t in tasks]
        for f in futures:
            try:
                raw.append(f.result())
            except Exception as e:  # 키 미설정, 네트워크 오류 등
                failures += 1
                last_err = f"{type(e).__name__}: {str(e)[:120]}"

    if failures == len(tasks):
        return [], [f"뉴스 조회에 모두 실패해 이슈 정보를 반영하지 못했습니다 ({last_err})"]
    if failures:
        warnings.append(f"뉴스 조회 일부 실패 ({failures}/{len(tasks)}건)")

    cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
    seen: set[str] = set()
    items: list[dict] = []
    for cat, kw, news_list in raw:
        for n in news_list:
            dt = _parse_pub_date(n.get("pub_date", ""))
            if dt is None or dt < cutoff:
                continue
            text = f"{n['title']} {n['description']}"
            # 지역과 무관한 기사 제거 (네이버 검색은 관련도가 낮은 기사도 섞여 나옴)
            if scope not in text:  # 세부 지역(예: 성남)을 말했으면 그 이름이 있는 기사만 (경기 전체 뉴스 제외)
                continue
            if not all(tok in text for tok in kw.split()):
                continue
            title_key = re.sub(r"\s+", "", n["title"])
            if title_key in seen or n["link"] in seen:
                continue
            seen.update([title_key, n["link"]])
            items.append({
                "category": cat,
                "keyword": kw,
                "title": n["title"],
                "description": n["description"],
                "link": n["link"],
                "_dt": dt,
            })

    items.sort(key=lambda x: x["_dt"], reverse=True)
    items = items[:max_items]
    for i, it in enumerate(items, 1):
        it["id"] = f"N{i}"
        it["pub_date"] = it.pop("_dt").astimezone().strftime("%Y-%m-%d %H:%M")
    return items, warnings


def _name_variants(title: str) -> set[str]:
    base = re.sub(r"\(.*?\)|\[.*?\]", "", title).strip()
    return {v for v in {base} if len(v) >= 3}  # 너무 짧은 이름은 오탐이 많아 제외


def flag_place_issues(places: list[dict], news_items: list[dict]) -> None:
    """
    장소 이름이 뉴스 제목/요약에 등장하면 place['related_news_ids']에 뉴스 id를 붙입니다.
    (places를 직접 수정합니다)
    """
    for p in places:
        names = _name_variants(p.get("title", ""))
        p["related_news_ids"] = [
            n["id"] for n in news_items
            if any(nm in f"{n['title']} {n['description']}" for nm in names)
        ]
