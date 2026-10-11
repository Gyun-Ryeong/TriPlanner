"""
일정 품질 지표 (개발자 모드·일괄 평가용).

챗봇이 만든 일정 하나를 아래 기준으로 수치화합니다. 화면에는 개발자 모드(관리자)에서만 보이고,
evaluate.py 가 같은 함수로 여러 질문의 결과를 모아 평균을 냅니다.

- 근거성(grounding): AI가 제안한 장소 중 후보 목록(실제 관광 데이터)에 없는 장소의 비율 = 지어낸 장소 비율
- 날씨 적합도: 궂은 날(비/눈·폭염·한파·미세먼지 나쁨)에 배치된 방문지 중 실내 장소의 비율
- 동선: 하루 방문지·식당을 순서대로 이은 직선거리 합 (km)
- 채움 정도: 방문지가 있는 날의 비율, 하루 평균 방문지 수, 방문지 유형 다양성
"""
from travel.geo import straight_km


def _round(x: float | None, n: int = 2) -> float | None:
    return None if x is None else round(x, n)


def _day_distance_km(day: dict) -> float:
    """방문지와 식당을 시간표 순서대로 이은 직선거리 합. 좌표가 없는 장소는 건너뛴다."""
    stops = [e["place"] for e in day["events"] if e["kind"] in ("visit", "meal") and e.get("place")]
    total = 0.0
    for a, b in zip(stops, stops[1:]):
        km = straight_km(a, b)
        if km is not None:
            total += km
    return total


def evaluate_plan(days_view: list[dict], grounding: dict, source: str, timings: dict | None = None) -> dict:
    """
    Args:
        days_view: hydrate_plan() 결과
        grounding: normalize_plan() 이 채운 {"proposed": AI가 제안한 장소 수, "dropped": 후보에 없어 버린 수}
        source: "llm"(AI 일정) | "fallback"(AI 실패로 규칙 기반 기본 일정)
        timings: 응답 소요 시간 (collect_sec·rank_sec·llm_sec)
    """
    proposed, dropped = grounding.get("proposed", 0), grounding.get("dropped", 0)

    bad_days = [d for d in days_view if d["outdoor_ok"] is False]
    bad_visits = sum(len(d["items"]) for d in bad_days)
    bad_outdoor = sum(d["outdoor_count"] for d in bad_days)

    distances = [_day_distance_km(d) for d in days_view]
    visits = [len(d["items"]) for d in days_view]
    types = {item["place"]["type"] for d in days_view for item in d["items"] if item["place"].get("type")}

    total_sec = None
    if timings:
        total_sec = round(sum(timings.get(k) or 0 for k in ("collect_sec", "rank_sec", "llm_sec")), 1)

    return {
        "source": source,
        "days": len(days_view),
        # 근거성: fallback 일정은 AI가 장소를 고르지 않았으므로 비율을 내지 않는다
        "proposed_places": proposed,
        "hallucinated_places": dropped,
        "hallucination_rate": _round(dropped / proposed) if source == "llm" and proposed else None,
        # 날씨 적합도: 궂은 날이 없으면 판단 대상이 아니다
        "bad_weather_days": len(bad_days),
        "bad_weather_visits": bad_visits,
        "bad_weather_outdoor_visits": bad_outdoor,
        "weather_fit_rate": _round((bad_visits - bad_outdoor) / bad_visits) if bad_visits else None,
        # 동선
        "daily_distance_km": [_round(x, 1) for x in distances],
        "avg_daily_distance_km": _round(sum(distances) / len(distances), 1) if distances else None,
        # 채움 정도
        "filled_day_rate": _round(sum(1 for v in visits if v) / len(visits)) if visits else None,
        "avg_visits_per_day": _round(sum(visits) / len(visits), 1) if visits else None,
        "place_type_count": len(types),
        "response_sec": total_sec,
    }
