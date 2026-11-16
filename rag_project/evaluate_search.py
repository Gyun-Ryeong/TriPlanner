"""
장소 검색 정확도 평가 (Ollama·외부 API 없이, 벡터 DB만으로 1분 안팎).

eval/search_cases.json 의 질문마다 그 시도의 장소를 실제 일정과 같은 함수(rank_places)로 줄 세우고,
상위 5곳 중 '정답 기준(expect 정규식)'에 맞는 장소 비율을 잽니다. 정답 기준은 이름·분류·소개글에 대해 검사합니다.

  - P@5   : 상위 5곳 중 맞는 장소 비율 (정밀도)
  - Hit@5 : 상위 5곳 안에 맞는 장소가 하나라도 있으면 1
  - MRR   : 처음 맞는 장소 순위의 역수 평균 (1등이면 1, 2등이면 0.5 …)

벡터만 쓴 경우와 키워드를 섞은 경우(하이브리드)를 나란히 보여줘서, 바꾼 효과를 숫자로 확인합니다.

    python evaluate_search.py                 # 전체
    python evaluate_search.py --only daegu-gukbap,seoul-museum
결과: eval/results/search_YYYYMMDD_HHMMSS.md
"""
import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from collectors.tourism import cached_overview, category_label
from travel import context
from travel.ldong import resolve_ldong
from travel.place_db import PlaceDB

BASE = Path(__file__).parent / "eval"
K = 5


def _text(p: dict) -> str:
    return " ".join([p.get("title", ""), category_label(p.get("raw")), p.get("overview") or cached_overview(p.get("content_id"))])


def score(ranked: list[dict], expect: str) -> dict:
    pat = re.compile(expect)
    hits = [bool(pat.search(_text(p))) for p in ranked[:K]]
    first = next((i for i, h in enumerate(hits) if h), None)
    return {"p5": sum(hits) / K, "hit5": 1.0 if any(hits) else 0.0, "rr": 1 / (first + 1) if first is not None else 0.0,
            "top": [p["title"] for p in ranked[:K]], "hits": hits}


def run_case(db: PlaceDB, case: dict) -> dict:
    sido = case["sido"]
    places = db.get_places(resolve_ldong(sido)[0], types=set(case["types"]), sido=sido)
    query = f"{sido} {case['query']}"
    with patch.object(context, "_hybrid", lambda order, *a: order):
        vec = score(context.rank_places(places, sido, query), case["expect"])
    hyb = score(context.rank_places(places, sido, query), case["expect"])
    return {"id": case["id"], "query": query, "candidates": len(places), "vector": vec, "hybrid": hyb}


def _avg(rows: list[dict], mode: str, key: str) -> float:
    return round(sum(r[mode][key] for r in rows) / len(rows), 3) if rows else 0.0


def to_markdown(rows: list[dict], started_at: str) -> str:
    lines = [f"# 장소 검색 정확도 ({started_at})", "", f"질문 {len(rows)}개, 상위 {K}곳 기준", "",
             "| 지표 | 벡터만 | 키워드 섞기 | 설명 |", "|---|---|---|---|"]
    for key, name, desc in (("p5", "P@5", "상위 5곳 중 맞는 비율"), ("hit5", "Hit@5", "5곳 안에 하나라도 맞음"),
                            ("rr", "MRR", "처음 맞는 장소 순위의 역수 평균")):
        lines.append(f"| {name} | {_avg(rows, 'vector', key):.3f} | {_avg(rows, 'hybrid', key):.3f} | {desc} |")
    lines += ["", "## 질문별 (P@5)", "", "| 질문 | 후보 | 벡터만 | 키워드 섞기 | 키워드 섞기 상위 3곳 |", "|---|---|---|---|---|"]
    for r in rows:
        top = ", ".join(("✅" if h else "❌") + t[:14] for t, h in zip(r["hybrid"]["top"][:3], r["hybrid"]["hits"][:3]))
        lines.append(f"| {r['query']} | {r['candidates']} | {r['vector']['p5']:.1f} | {r['hybrid']['p5']:.1f} | {top} |")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="장소 검색 정확도 평가")
    parser.add_argument("--cases", default=str(BASE / "search_cases.json"))
    parser.add_argument("--only", default="")
    args = parser.parse_args()
    cases = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    if args.only:
        wanted = {x.strip() for x in args.only.split(",")}
        cases = [c for c in cases if c["id"] in wanted]

    db = PlaceDB()
    if not db.stats()["places"]:
        print("벡터 DB가 비어 있어요. 먼저 python build_vector_db.py 를 실행하세요.")
        return
    started_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    rows = []
    for i, case in enumerate(cases, 1):
        r = run_case(db, case)
        rows.append(r)
        print(f"[{i}/{len(cases)}] {case['id']}: 벡터 {r['vector']['p5']:.1f} → 섞기 {r['hybrid']['p5']:.1f}", flush=True)

    out_dir = BASE / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    md = to_markdown(rows, started_at)
    (out_dir / f"search_{stamp}.md").write_text(md, encoding="utf-8")
    (out_dir / f"search_{stamp}.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n" + md)
    print(f"저장: {out_dir / f'search_{stamp}.md'}")


if __name__ == "__main__":
    main()
