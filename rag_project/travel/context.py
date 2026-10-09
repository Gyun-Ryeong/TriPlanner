"""
일정 생성에 쓸 데이터 수집과 후보 선별.

- gather_raw()        : 관광정보 + 이슈 뉴스 + 날씨 + 미세먼지를 병렬로 수집 (외부 API 호출, 세션에서 재사용)
- select_candidates() : 취향과 유사한 후보를 벡터 검색으로 고르고, 궂은 날을 위한 실내 후보를 보장
"""
import time
from concurrent.futures import ThreadPoolExecutor, wait
from datetime import date

from config import GATHER_TIMEOUT_SEC, NEWS_DAYS_BACK, OVERVIEW_ENRICH_LIMIT
from collectors.air_quality import get_air_summary
from collectors.cache import pop_stale_events
from collectors.tourism import enrich_overviews
from travel.documents import place_text
from travel.embeddings import get_ranker
from travel.pipeline import _collect_candidates, _collect_weather
from travel.risk_scanner import flag_place_issues, scan_regional_risks


def gather_raw(sido: str, area: str, start: date, end: date, include_food: bool, today: date) -> dict:
    """
    한 번 모으면 같은 여행 조건에서는 취향이 바뀌어도 재사용합니다.
    네 가지(관광정보·뉴스·날씨·미세먼지)를 동시에 호출하고, GATHER_TIMEOUT_SEC 안에 끝나지 않은 항목은 빼고 진행합니다.
    (늦는 호출은 백그라운드에서 끝나 캐시에 남으므로 다음 요청에서는 빨라집니다)
    """
    warnings: list[str] = []
    timings: dict[str, float] = {}

    def timed(label, fn):
        def run():
            t0 = time.perf_counter()
            try:
                return fn()
            finally:
                timings[label] = round(time.perf_counter() - t0, 1)
        return run

    ex = ThreadPoolExecutor(max_workers=4)
    futs = {
        "places": ex.submit(timed("places", lambda: _collect_candidates(sido, start, end, include_food, area))),
        "news": ex.submit(timed("news", lambda: scan_regional_risks(sido, area=area, days_back=NEWS_DAYS_BACK))),
        "weather": ex.submit(timed("weather", lambda: _collect_weather(sido, start, end, today))),
        "air": ex.submit(timed("air", lambda: get_air_summary(sido, start, end, today))),
    }
    done, _pending = wait(list(futs.values()), timeout=GATHER_TIMEOUT_SEC)
    ex.shutdown(wait=False)  # 늦는 작업은 기다리지 않는다

    def result(label, default, name):
        f = futs[label]
        if f not in done:
            warnings.append(f"{name} 조회가 {GATHER_TIMEOUT_SEC:.0f}초 안에 끝나지 않아 이번에는 반영하지 못했어요. 잠시 뒤 다시 요청하면 반영될 수 있어요.")
            return default
        try:
            return f.result()
        except Exception as e:
            warnings.append(f"{name} 수집 중 오류: {type(e).__name__}: {str(e)[:100]}")
            return default

    places, w = result("places", ([], []), "관광정보")
    warnings += w
    news, w = result("news", ([], []), "뉴스")
    warnings += w
    weather, wstatus, werr = result("weather", ([], "error", ""), "날씨")
    air = result("air", {"by_date": {}, "realtime": None, "warnings": []}, "미세먼지")

    if wstatus == "error":
        warnings.append(f"날씨 조회 실패로 날씨를 반영하지 못했습니다 ({werr})")
    warnings += air.get("warnings", [])
    warnings += pop_stale_events()

    flag_place_issues(places, news)
    return {
        "sido": sido, "area": area, "start": start.isoformat(), "end": end.isoformat(),
        "include_food": include_food, "places": places, "news": news,
        "weather": weather, "weather_status": wstatus, "air": air,
        "warnings": warnings, "fetched_at": time.time(), "timings": dict(timings),
    }


def _keyword_rank(places: list[dict], query: str) -> list[dict]:
    """벡터DB를 쓸 수 없을 때의 대체 순위: 질문 글자와 겹치는 정도."""
    q = set(query.replace(" ", ""))
    return sorted(places, key=lambda p: -len(q & set((p["title"] + p["addr"]).replace(" ", ""))))


def rank_places(places: list[dict], sido: str, query: str, ranker=None) -> list[dict]:
    """
    취향(query)과 유사한 순서로 정렬. 한 번 계산한 장소 임베딩은 파일에 저장해 재사용합니다.
    임베딩을 쓸 수 없으면(패키지 문제 등) 키워드 순위로 대체합니다.
    """
    if not places:
        return []
    by_key = {(p["content_id"] or p["title"]): p for p in places}
    try:
        ranker = ranker or get_ranker()
        order = ranker.rank([(k, place_text(p, sido)) for k, p in by_key.items()], query)
        return [by_key[k] for k in order]
    except Exception:
        return _keyword_rank(places, query)


def select_candidates(ranked: list[dict], k: int, need_indoor: int, type_caps: dict[str, int] | None = None) -> list[dict]:
    """
    유사도 순으로 k개를 고릅니다.
    - type_caps: 유형별 상한 (예: {"28": 3} → 레포츠는 최대 3곳). 후보가 모자라면 상한에 걸려 빠진 것으로 채웁니다.
    - need_indoor: 비/미세먼지로 실내 위주인 날을 위해 실내 후보를 최소 이만큼 보장합니다.
    """
    caps = type_caps or {}
    counts: dict[str, int] = {}
    chosen: list[dict] = []
    skipped: list[dict] = []
    for p in ranked:
        if len(chosen) >= k:
            break
        t = str(p.get("content_type_id", ""))
        if t in caps and counts.get(t, 0) >= caps[t]:
            skipped.append(p)
            continue
        counts[t] = counts.get(t, 0) + 1
        chosen.append(p)
    for p in skipped:  # 상한 때문에 모자라면 순위대로 채움
        if len(chosen) >= k:
            break
        chosen.append(p)

    have = sum(1 for p in chosen if p.get("indoor"))
    if have < need_indoor:
        in_chosen = {id(p) for p in chosen}
        for p in ranked:
            if id(p) not in in_chosen and p.get("indoor"):
                chosen.append(p)
                have += 1
                if have >= need_indoor:
                    break
    return chosen


def enrich(places: list[dict]) -> list[str]:
    """선택된 후보에만 소개글을 붙입니다(호출 수 절약, 캐시됨)."""
    return enrich_overviews(places, OVERVIEW_ENRICH_LIMIT)
