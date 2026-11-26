"""
연합뉴스 재난·사건사고 기사 (행정안전부 재난안전데이터 공유플랫폼, DSSP-IF-10747).

- 화재·교통사고·침몰·호우 대비·안전 점검 같은 재난·안전 기사만 모은 데이터라, 사건·사고 질문과 여행 지역 이슈에 쓴다.
- 날짜로 거르는 변수가 없고 오래된 기사부터 나온다 → 전체 건수를 보고 마지막 페이지들(가장 최근 기사)을 받는다.
  (2026-11 기준 1,000건 ≈ 3주, 하루 평균 약 44건)
- 기사 링크(URL)가 없어서 화면에는 '출처: 연합뉴스'로 보여준다.
- 등록한 IP에서만 호출된다 (플랫폼 인증키 관리에서 IP 등록). 막히면 빈 목록 + 경고 → 네이버 뉴스만으로 동작.

반환 형식은 네이버 뉴스(search_news)와 같다: {"title", "description", "link", "pub_date", "source", "dateline"}
"""
import re
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime

import requests

import config
from collectors.cache import ttl_cache

KST = timezone(timedelta(hours=9))
PAGE_ROWS = 1000
PAGES = 2  # 최근 2,000건 ≈ 한 달 반
_DATELINE_RE = re.compile(r"\(([^()=\n]{1,12})=연합뉴스\)")


class YonhapError(Exception):
    pass


def _call(page: int, rows: int) -> dict:
    if not config.YONHAP_NEWS_API_KEY:
        raise YonhapError("YONHAP_NEWS_API_KEY 가 .env 에 없어요.")
    params = {"serviceKey": config.YONHAP_NEWS_API_KEY, "returnType": "json", "pageNo": page, "numOfRows": rows}
    try:
        resp = requests.get(config.ENDPOINTS["yonhap_news"], params=params, timeout=20)
        data = resp.json()
    except (requests.RequestException, ValueError) as e:
        raise YonhapError(f"연합뉴스 API 호출 실패: {type(e).__name__}") from None
    head = data.get("header") or {}
    if str(head.get("resultCode")) != "00":
        hint = " (재난안전데이터 공유플랫폼에 이 PC·서버의 IP를 등록하세요)" if str(head.get("resultCode")) == "32" else ""
        raise YonhapError(f"연합뉴스 API 오류 {head.get('resultCode')}: {head.get('errorMsg') or head.get('resultMsg')}{hint}")
    return data


def _to_item(row: dict) -> dict | None:
    title = str(row.get("YNA_TTL") or "")
    # 지운 기사는 DEL_YN 이 그대로 N 이고 제목에 '<삭제>' 가 붙어 온다
    if row.get("DEL_YN") == "Y" or not title.strip() or "<삭제>" in title:
        return None
    try:
        dt = datetime.strptime(str(row.get("CRT_DT", "")), "%Y/%m/%d %H:%M:%S").replace(tzinfo=KST)
    except ValueError:
        try:
            dt = datetime.strptime(str(row.get("YNA_REG_YMD", "")), "%Y-%m-%d").replace(tzinfo=KST)
        except ValueError:
            return None
    body = str(row.get("YNA_CN") or "")
    m = _DATELINE_RE.search(body)
    # 본문은 '제목 + (부산=연합뉴스) 홍길동 기자 = 본문 … (끝)' 모양. 요약에는 기자 이름 뒤부터 쓴다
    text = body[m.end():] if m else body
    text = re.sub(r"^\s*[^=\n]{0,30}기자\s*=\s*", "", text)
    text = re.sub(r"\S+@yna\.co\.kr|\(끝\)", " ", text)
    # 화면의 '본문 보기'용: 문단(줄)은 살리고 빈 줄·앞뒤 공백만 정리
    paragraphs = [re.sub(r"[ \t]+", " ", ln).strip() for ln in text.splitlines()]
    full = "\n".join(p for p in paragraphs if p)
    text = re.sub(r"\s+", " ", text).strip()
    return {
        "title": str(row["YNA_TTL"]).strip(),
        "description": text,
        "body": full,
        "link": "",
        "pub_date": format_datetime(dt),  # 네이버 뉴스와 같은 RFC 2822 형식
        "source": "연합뉴스",
        "dateline": m.group(1).strip() if m else "",
        "yna_no": row.get("YNA_NO"),
    }


@ttl_cache("yonhap", 30 * 60, stale_ttl=24 * 3600, fail_cooldown=300)
def recent_articles(pages: int = PAGES) -> list[dict]:
    """가장 최근 기사 (최신순). 30분 저장, 실패하면 하루 안의 저장본."""
    total = int(_call(1, 1).get("totalCount") or 0)
    if total <= 0:
        return []
    last = (total - 1) // PAGE_ROWS + 1
    rows: list[dict] = []
    for page in range(last, max(0, last - pages), -1):
        rows += _call(page, PAGE_ROWS).get("body") or []
    items = [it for it in (_to_item(r) for r in rows) if it]
    items.sort(key=lambda it: it.get("yna_no") or 0, reverse=True)  # 기사 번호는 시간순으로 커진다
    return items


def _similar_title(a: str, b: str) -> float:
    """두 제목의 글자 두 개 묶음 겹침 비율 (0~1)"""
    def grams(s):
        s = re.sub(r"[\s\W_]+", "", s or "")
        return {s[i:i + 2] for i in range(len(s) - 1)}
    x, y = grams(a), grams(b)
    return len(x & y) / len(x | y) if x and y else 0.0


@ttl_cache("yna_link", 7 * 24 * 3600)
def _find_link(title: str) -> dict:
    """같은 연합뉴스 기사의 원문 주소를 네이버 뉴스 검색으로 찾는다 (yna.co.kr 이고 제목이 비슷한 것)"""
    from collectors.naver_news import search_news
    best, best_score = "", 0.0
    for it in search_news(title, display=10, sort="sim"):
        link = it.get("link") or ""
        if "yna.co.kr" not in link:
            continue
        score = _similar_title(title, it.get("title", ""))
        if score > best_score:
            best, best_score = link, score
    return {"link": best if best_score >= 0.5 else ""}  # 빈 값도 저장 (못 찾은 기사를 7일간 다시 찾지 않음)


def attach_links(items: list[dict], limit: int = 8) -> None:
    """
    링크가 없는 연합뉴스 기사에 원문 주소를 붙인다 (제자리에서). 기사당 네이버 검색 1번, 7일 저장.
    못 찾으면 그대로 둔다 (화면에서 '본문 보기'). 네이버 키가 없거나 검색이 실패해도 예외를 내지 않는다.
    """
    todo = [it for it in items if it.get("source") == "연합뉴스" and not it.get("link")][:limit]
    for it in todo:
        try:
            it["link"] = _find_link(it["title"])["link"]
        except Exception:
            pass


def matches_region(item: dict, name: str) -> bool:
    """지역 이름이 제목이나 데이트라인((부산=연합뉴스))에 있는지 (띄어쓰기 무시)"""
    key = re.sub(r"\s+", "", name or "")
    return bool(key) and (key in re.sub(r"\s+", "", item["title"]) or key in item.get("dateline", ""))
