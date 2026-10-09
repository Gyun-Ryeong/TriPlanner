"""
네이버 뉴스 검색 API + 검색어 트렌드 API (NAVER API HUB)

  호출 주소  https://naverapihub.apigw.ntruss.com
  인증 헤더  X-NCP-APIGW-API-KEY-ID (= Client ID), X-NCP-APIGW-API-KEY (= Client Secret)
  키 위치    네이버 클라우드 콘솔 > NAVER API HUB > Application > 해당 앱의 [인증 정보]
             (Application의 API 목록에 '뉴스'가 등록돼 있어야 함)
"""
import html
import json
import re
import threading
import time

import requests
from collectors.cache import ttl_cache
from config import ENDPOINTS, NAVER_CLIENT_ID, NAVER_CLIENT_SECRET


def _headers() -> dict:
    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
        raise ValueError("NAVER_CLIENT_ID / NAVER_CLIENT_SECRET이 설정되지 않았습니다. "
                         "NAVER API HUB의 [인증 정보] 값을 .env에 넣어주세요.")
    return {"X-NCP-APIGW-API-KEY-ID": NAVER_CLIENT_ID, "X-NCP-APIGW-API-KEY": NAVER_CLIENT_SECRET}


# 짧은 시간에 호출이 몰리면 429(Too Many Requests)가 나므로, 여러 스레드가 동시에 불러도
# 호출 사이에 최소 간격을 두어 초당 약 8회 이하로 맞춥니다.
_MIN_INTERVAL = 0.12
_rate_lock = threading.Lock()
_last_call = 0.0


def _throttle() -> None:
    global _last_call
    with _rate_lock:
        wait = _MIN_INTERVAL - (time.monotonic() - _last_call)
        if wait > 0:
            time.sleep(wait)
        _last_call = time.monotonic()


def _call(method: str, url: str, *, params=None, data=None, extra_headers=None):
    """호출하고, 429(호출 과다)면 잠깐 쉬었다가 최대 2번 재시도합니다."""
    headers = {**_headers(), **(extra_headers or {})}
    send = requests.get if method == "GET" else requests.post
    resp = None
    for attempt in range(3):
        _throttle()
        resp = send(url, headers=headers, params=params, data=data, timeout=10)
        if resp.status_code == 429 and attempt < 2:
            time.sleep(1.0 * (attempt + 1))
            continue
        break
    return resp


def _raise_for_error(resp) -> None:
    if resp.status_code < 400:
        return
    try:
        body = resp.json()
        detail = body.get("errorMessage") or (body.get("error") or {}).get("message") or body.get("message") or resp.text
    except (ValueError, AttributeError):
        detail = resp.text
    hint = ""
    if resp.status_code in (401, 403):
        hint = " → [인증 정보]의 Client ID/Secret 값과 Application의 '뉴스' API 등록 여부를 확인하세요"
    raise requests.HTTPError(f"NAVER API HUB 오류 {resp.status_code}: {str(detail)[:150]}{hint}")


def _clean(text: str) -> str:
    """응답의 <b> 태그와 HTML 엔티티(&quot; &amp; 등)를 정리."""
    return re.sub(r"<[^>]+>", "", html.unescape(text or "")).strip()


@ttl_cache("news", 600, stale_ttl=6 * 3600, fail_cooldown=120)
def search_news(query: str, display: int = 10, sort: str = "date") -> list[dict]:
    """
    네이버 뉴스 검색.

    Args:
        query: 검색어
        display: 결과 개수 (최대 100)
        sort: "date"(최신순) 또는 "sim"(정확도순)
    """
    params = {"query": query, "display": display, "sort": sort}
    resp = _call("GET", ENDPOINTS["naver_news_hub"], params=params)
    _raise_for_error(resp)
    items = resp.json().get("items", [])

    results = []
    for item in items:
        results.append({
            "source": "naver_news",
            "title": _clean(item.get("title", "")),
            "description": _clean(item.get("description", "")),
            "link": item.get("originallink", item.get("link", "")),
            "pub_date": item.get("pubDate", ""),
            "raw": item,
        })
    return results


def get_search_trend(keyword_groups: list[dict], start_date: str, end_date: str, time_unit: str = "date") -> dict:
    """
    검색어 트렌드 조회 (POST 요청, JSON 바디 필요).

    Args:
        keyword_groups: [{"groupName": "그룹명", "keywords": ["검색어1", "검색어2"]}, ...] (최대 5개 그룹)
        start_date: "YYYY-MM-DD"
        end_date: "YYYY-MM-DD"
        time_unit: "date" | "week" | "month"
    """
    body = {"startDate": start_date, "endDate": end_date, "timeUnit": time_unit, "keywordGroups": keyword_groups}
    resp = _call("POST", ENDPOINTS["naver_datalab_hub"], data=json.dumps(body),
                 extra_headers={"Content-Type": "application/json"})
    _raise_for_error(resp)
    return resp.json()
