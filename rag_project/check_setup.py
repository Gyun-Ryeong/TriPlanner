"""
단계별 점검 스크립트.

전체 실행:      python check_setup.py
특정 단계만:    python check_setup.py ollama
                python check_setup.py apis
                python check_setup.py vector
                python check_setup.py e2e
                python check_setup.py travel     # 여행지 추천 전체 흐름 (실제 API + Ollama 사용)
                python check_setup.py chat       # 대화형 플래너 (실제 API + Ollama 사용)

각 단계는 독립적이라 앞 단계가 실패해도 다음 단계를 계속 시도합니다.
"""
import os
import sys
import time
import traceback

import requests

os.environ.setdefault("DEV_MODE", "on")  # 점검용이라 내부 정보(제약사항·소요 시간)를 보여준다 (config import 전에 설정)
from config import OLLAMA_BASE_URL, OLLAMA_MODEL


def _report(name: str, ok: bool, detail: str = "") -> None:
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {name}" + (f" - {detail}" if detail else ""))


# ── 1. Ollama ────────────────────────────────────────────────────────
def check_ollama() -> None:
    print("\n=== 1. Ollama 연결 ===")
    try:
        r = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        r.raise_for_status()
        names = [m["name"] for m in r.json().get("models", [])]
        _report("서버 연결", True, f"설치된 모델: {names or '없음'}")
        if OLLAMA_MODEL not in names:
            print(f"  ! 주의: OLLAMA_MODEL='{OLLAMA_MODEL}' 이(가) 목록에 없습니다. "
                  "클라우드 모델이면 무시해도 되고, 로컬 모델이면 ollama pull 이 필요합니다.")
    except Exception as e:
        _report("서버 연결", False, str(e))
        return

    try:
        payload = {
            "model": OLLAMA_MODEL,
            "messages": [{"role": "user", "content": 'JSON으로만 답해: {"ok": true}'}],
            "stream": False,
            "format": "json",
        }
        r = requests.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload, timeout=180)
        if r.status_code >= 400:
            _report("chat + format=json", False, f"HTTP {r.status_code} / Ollama 메시지: {r.text[:400]}")
            print("  → 위 'Ollama 메시지'가 실제 원인입니다. 메모리 부족이면 더 작은 모델을 쓰세요.")
            return
        content = r.json().get("message", {}).get("content", "")
        _report("chat + format=json", True, f"응답: {content[:80]}")
    except Exception as e:
        _report("chat + format=json", False, str(e))


# ── 2. 공공데이터 / 네이버 API ────────────────────────────────────────
def check_apis() -> None:
    print("\n=== 2. 외부 API (여행 플래너가 쓰는 것만) ===")
    print("  ※ 실패 원인이 키인지 API인지 자세히 보려면: python diagnose_api.py")
    from datetime import date, timedelta
    from collectors import get_air_summary, get_short_term_forecast, get_tourism_info, search_news
    from travel.ldong import resolve_ldong

    today = date.today()

    def tour():
        code, _ = resolve_ldong("부산")
        return get_tourism_info(l_dong_regn_cd=code, content_type_id="12", num_rows=3)

    def air():
        res = get_air_summary("부산", today, today + timedelta(days=1), today)
        if res["warnings"] and not res["by_date"]:
            raise RuntimeError(res["warnings"][0])
        return list(res["by_date"])

    tests = {
        "관광정보(TourAPI)": tour,
        "단기예보(기상청)": lambda: get_short_term_forecast("서울"),
        "미세먼지(에어코리아)": air,
        "네이버뉴스": lambda: search_news("날씨", display=3),
    }
    for name, fn in tests.items():
        try:
            items = fn()
            _report(name, len(items) > 0, f"{len(items)}건")
            if not items:
                print("  ! 0건: python diagnose_api.py 로 원인을 확인하세요.")
        except Exception as e:
            _report(name, False, f"{type(e).__name__}: {str(e)[:150]}")


# ── 3. 벡터 DB ───────────────────────────────────────────────────────
def check_vector() -> None:
    print("\n=== 3. 임베딩 + 벡터DB ===")
    try:
        from rag.vector_store import VectorStore
        from rag.document_builder import build_documents

        store = VectorStore(collection_name="setup_check")
        items = [
            {"title": "경복궁", "addr": "서울 종로구"},
            {"title": "해운대", "addr": "부산 해운대구"},
            {"title": "성산일출봉", "addr": "제주 서귀포시"},
        ]
        store.add_documents(build_documents("tourism", items))
        hits = store.search("부산 바다", top_k=1)
        top = hits[0]["text"] if hits else ""
        _report("적재/검색", "해운대" in top, f"1위 결과: {top}")
        store.clear()
    except Exception:
        _report("적재/검색", False)
        traceback.print_exc()


# ── 4. 전체 흐름 (API 없이 더미 문서로) ───────────────────────────────
def check_e2e() -> None:
    print("\n=== 4. 답변 생성 (더미 문서 사용) ===")
    try:
        from llm.ollama_client import ask_with_caveats

        docs = [
            {"text": "[대기질-서울 종로구] 측정시각: 2026-09-28 10:00, PM10: 45, PM2.5: 20, 통합대기환경지수 등급: 2",
             "metadata": {"source": "air_quality"}},
        ]
        result = ask_with_caveats("서울 미세먼지 어때?", docs)
        _report("JSON 구조", all(k in result for k in ("answer", "caveats", "used_sources")))
        print(f"  answer  : {result['answer'][:100]}")
        print(f"  caveats : {result['caveats']}")
        print(f"  sources : {result['used_sources']}")
    except Exception as e:
        _report("답변 생성", False, f"{type(e).__name__}: {e}")


# ── 5. 여행지 추천 전체 흐름 ───────────────────────────────────────────
def check_travel() -> None:
    print("\n=== 5. 여행지 추천 전체 흐름 (부산, 내일~모레) ===")
    try:
        from datetime import date, timedelta
        from travel.pipeline import recommend_trip

        today = date.today()
        res = recommend_trip("부산", today + timedelta(days=1), today + timedelta(days=2),
                             preferences="바다 산책", top_n=3)
        m = res["meta"]
        _report("후보 수집", m["candidates"] > 0, f"{m['candidates']}곳")
        _report("이슈 뉴스", True, f"{m['news_items']}건 (0건이어도 정상일 수 있음)")
        _report("날씨", bool(res["weather"]), f"{len(res['weather'])}일치")
        _report("LLM JSON", m.get("llm_json_ok", False))
        print(f"  summary : {res['summary'][:100]}")
        for r in res["recommendations"]:
            print(f"  {r['rank']}. {r['name']} - {r['reason'][:60]}")
        print("  caveats :")
        for c in res["caveats"]:
            print(f"    - {c[:110]}")
    except Exception:
        _report("여행 추천", False)
        traceback.print_exc()


# ── 6. 대화형 플래너 (실제 API + Ollama 사용) ───────────────────────────
def check_chat() -> None:
    print("\n=== 6. 대화형 플래너 (부산, 내일부터 2박 3일) ===")
    try:
        from travel.chat import ChatSession, handle_message

        from travel.embeddings import get_ranker

        t0 = time.time()
        get_ranker().load()
        print(f"  (임베딩 모델 로딩 {time.time() - t0:.1f}초 — 채팅 화면/API 서버에서는 켜질 때 한 번만 걸려요)")

        session = ChatSession()
        for msg in ["부산 가려고요", "내일부터 2박 3일이요", "커플이고 바다 보면서 조용히 걷고 싶어요"]:
            t0 = time.time()
            res = handle_message(session, msg)
            print(f"\n  👤 {msg}\n  🤖 [{res['stage']}] (걸린 시간 {time.time() - t0:.1f}초) {res['reply'][:1200]}")
            if res.get("timings"):
                tm, st = res["timings"], res.get("llm_stats") or {}
                tasks = ", ".join(f"{k} {v}초" for k, v in (tm.get("tasks") or {}).items())
                print(f"  ⏱ 데이터 수집 {tm['collect_sec']}초 [{tasks}] / 후보 검색 {tm['rank_sec']}초 / AI 일정 {tm['llm_sec']}초"
                      f"  (AI: 생성 {st.get('gen_tokens')}토큰, 초당 {st.get('tokens_per_sec')}토큰, 생각 {st.get('thinking_chars')}자)")
                if (st.get("thinking_chars") or 0) > 500:
                    print("  💡 모델이 답하기 전에 '생각'하는 데 시간을 많이 썼어요. .env에 OLLAMA_THINK=false 를 넣으면 줄어들 수 있어요.")
        n_places = sum(1 for d in (res["plan"] or []) for it in d["items"] if it["place"])
        _report("일정 생성", res["stage"] == "planned" and n_places > 0, f"일정에 들어간 장소 {n_places}곳")
        if res["conditions"]:
            for c in res["conditions"]:
                print(f"  {c['label']}: {c['recommend']} {c['bad_reasons']}")
        print("  제약사항:")
        for c in res["caveats"]:
            print(f"    - {c[:110]}")
    except Exception:
        _report("대화형 플래너", False)
        traceback.print_exc()


STEPS = {"ollama": check_ollama, "apis": check_apis, "vector": check_vector,
         "e2e": check_e2e, "travel": check_travel, "chat": check_chat}

if __name__ == "__main__":
    targets = sys.argv[1:] or list(STEPS)
    for t in targets:
        if t not in STEPS:
            print(f"알 수 없는 단계: {t} (가능: {', '.join(STEPS)})")
            continue
        STEPS[t]()
