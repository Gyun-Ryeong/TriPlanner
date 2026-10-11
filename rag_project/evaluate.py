"""
챗봇 일정 품질 일괄 평가.

eval/cases.json 의 질문들을 실제 챗봇 흐름(데이터 수집 + Ollama)으로 돌려서, 일정마다 품질 지표
(travel/evaluation.py, 개발자 모드 화면과 같은 값)를 모으고 평균을 냅니다.
결과는 eval/results/ 에 JSON(전체 값)과 Markdown(요약 표)으로 저장합니다.

    python evaluate.py              # 전체 케이스
    python evaluate.py --limit 3    # 앞에서 3개만 (빠른 확인용)
    python evaluate.py --only busan-couple-sea,daegu-indoor

필요한 것: .env 의 API 키 + 실행 중인 Ollama (채팅 화면과 같음). 케이스당 수십 초~몇 분 걸립니다.
"""
import argparse
import json
import time
from datetime import datetime
from pathlib import Path

from travel.chat import ChatSession, handle_message

BASE = Path(__file__).parent / "eval"
# 동행·취향을 되묻는 질문에는 이 답으로 넘어간다 (케이스 메시지를 다 보낸 뒤에도 일정이 안 나왔을 때)
SKIP_ANSWER = "상관없어요"
MAX_SKIPS = 2


def run_case(case: dict) -> dict:
    session = ChatSession()
    started = time.perf_counter()
    result, error = None, None
    try:
        for message in case["messages"]:
            result = handle_message(session, message, debug=True)
        skips = 0
        while result["stage"] == "asking" and skips < MAX_SKIPS:
            result = handle_message(session, SKIP_ANSWER, debug=True)
            skips += 1
    except Exception as e:  # 한 케이스가 실패해도 나머지는 계속 평가한다
        error = f"{type(e).__name__}: {str(e)[:300]}"
    wall_sec = round(time.perf_counter() - started, 1)

    evaluation = (result or {}).get("evaluation")
    # 여러 지역 일정은 지역별 지표를 각각 한 건으로 센다
    if evaluation and "regions" in evaluation:
        plans = [{"region": label, **ev} for label, ev in evaluation["regions"].items() if ev]
    else:
        plans = [evaluation] if evaluation else []
    return {
        "id": case["id"], "tags": case.get("tags", []), "messages": case["messages"],
        "stage": (result or {}).get("stage"), "wall_sec": wall_sec, "error": error,
        "caveats": (result or {}).get("caveats", []), "plans": plans,
    }


def _mean(values: list) -> float | None:
    values = [v for v in values if v is not None]
    return round(sum(values) / len(values), 3) if values else None


def summarize(results: list[dict]) -> dict:
    plans = [p for r in results for p in r["plans"]]
    llm_plans = [p for p in plans if p["source"] == "llm"]
    return {
        "cases": len(results),
        "cases_with_plan": sum(1 for r in results if r["plans"]),
        "cases_failed": sum(1 for r in results if r["error"]),
        "plans": len(plans),
        "fallback_rate": round(1 - len(llm_plans) / len(plans), 3) if plans else None,
        # 근거성: AI 일정 전체에서 지어낸 장소 수 / 제안한 장소 수 (일정별 평균이 아니라 전체 합으로 계산)
        "hallucination_rate": (round(sum(p["hallucinated_places"] for p in llm_plans)
                                     / sum(p["proposed_places"] for p in llm_plans), 3)
                               if sum(p["proposed_places"] for p in llm_plans) else None),
        "plans_with_bad_weather": sum(1 for p in plans if p["bad_weather_days"]),
        "weather_fit_rate": _mean([p["weather_fit_rate"] for p in plans]),
        "avg_daily_distance_km": _mean([p["avg_daily_distance_km"] for p in plans]),
        "filled_day_rate": _mean([p["filled_day_rate"] for p in plans]),
        "avg_visits_per_day": _mean([p["avg_visits_per_day"] for p in plans]),
        "avg_place_type_count": _mean([p["place_type_count"] for p in plans]),
        "avg_response_sec": _mean([p["response_sec"] for p in plans]),
        "avg_wall_sec_per_case": _mean([r["wall_sec"] for r in results]),
    }


def _fmt(v, pct=False) -> str:
    if v is None:
        return "-"
    return f"{v * 100:.1f}%" if pct else str(v)


def to_markdown(summary: dict, results: list[dict], started_at: str) -> str:
    s = summary
    lines = [
        f"# 챗봇 일정 품질 평가 ({started_at})", "",
        "## 요약", "",
        "| 지표 | 값 | 설명 |", "|---|---|---|",
        f"| 케이스 | {s['cases']} (일정 생성 {s['cases_with_plan']}, 오류 {s['cases_failed']}) | 일정 {s['plans']}건 |",
        f"| 지어낸 장소 비율 | {_fmt(s['hallucination_rate'], True)} | AI가 제안한 장소 중 후보(실제 데이터)에 없던 비율 |",
        f"| 규칙 기반 대체 비율 | {_fmt(s['fallback_rate'], True)} | AI 실패로 기본 일정을 쓴 비율 |",
        f"| 궂은 날 실내 비율 | {_fmt(s['weather_fit_rate'], True)} | 궂은 날이 있던 일정 {s['plans_with_bad_weather']}건 기준 |",
        f"| 하루 이동 거리 | {_fmt(s['avg_daily_distance_km'])} km | 방문지·식당 순서대로 직선거리 합의 평균 |",
        f"| 일정이 채워진 날 | {_fmt(s['filled_day_rate'], True)} | 방문지가 1곳 이상인 날의 비율 |",
        f"| 하루 방문지 수 | {_fmt(s['avg_visits_per_day'])} | |",
        f"| 방문지 유형 수 | {_fmt(s['avg_place_type_count'])} | 일정 하나에 들어간 관광지·문화시설 등 유형 수 |",
        f"| 일정 생성 시간 | {_fmt(s['avg_response_sec'])} 초 | 수집 + 후보 선별 + AI 생성 |",
        f"| 케이스당 전체 시간 | {_fmt(s['avg_wall_sec_per_case'])} 초 | 대화 여러 턴 포함 |",
        "", "## 케이스별", "",
        "| 케이스 | 출처 | 지어낸 장소 | 궂은 날 실내 | 하루 거리(km) | 하루 방문지 | 생성(초) | 비고 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        if not r["plans"]:
            note = r["error"] or f"일정 없음 (stage={r['stage']})"
            lines.append(f"| {r['id']} | - | - | - | - | - | - | {note} |")
        for p in r["plans"]:
            name = f"{r['id']} ({p['region']})" if p.get("region") else r["id"]
            lines.append(
                f"| {name} | {p['source']} | {p['hallucinated_places']}/{p['proposed_places']} "
                f"| {_fmt(p['weather_fit_rate'], True)} | {_fmt(p['avg_daily_distance_km'])} "
                f"| {_fmt(p['avg_visits_per_day'])} | {_fmt(p['response_sec'])} | |"
            )
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="챗봇 일정 품질 일괄 평가")
    parser.add_argument("--cases", default=str(BASE / "cases.json"))
    parser.add_argument("--limit", type=int, default=0, help="앞에서 N개만 실행")
    parser.add_argument("--only", default="", help="쉼표로 구분한 케이스 id만 실행")
    args = parser.parse_args()

    cases = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    if args.only:
        wanted = {x.strip() for x in args.only.split(",")}
        cases = [c for c in cases if c["id"] in wanted]
    if args.limit:
        cases = cases[:args.limit]

    started_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    results = []
    for i, case in enumerate(cases, 1):
        print(f"[{i}/{len(cases)}] {case['id']} ...", flush=True)
        r = run_case(case)
        results.append(r)
        status = r["error"] or ", ".join(f"{p['source']} 지어낸 {p['hallucinated_places']}/{p['proposed_places']}" for p in r["plans"]) or "일정 없음"
        print(f"    {r['wall_sec']}초 · {status}", flush=True)

    summary = summarize(results)
    out_dir = BASE / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    (out_dir / f"eval_{stamp}.json").write_text(
        json.dumps({"started_at": started_at, "summary": summary, "results": results}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    md = to_markdown(summary, results, started_at)
    (out_dir / f"eval_{stamp}.md").write_text(md, encoding="utf-8")
    print("\n" + md)
    print(f"저장: {out_dir / f'eval_{stamp}.md'}")


if __name__ == "__main__":
    main()
