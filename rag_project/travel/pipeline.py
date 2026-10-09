"""
여행지 추천 RAG 파이프라인.

흐름
  1) 후보 수집   : TourAPI(관광지/문화시설/레포츠/축제) → 후보 장소
  2) 이슈 수집   : 네이버 뉴스에서 특보/취소/통제 기사 검색 → 후보 장소와 이름 매칭
  3) 날씨 수집   : 여행일이 예보 범위(약 3일) 안이면 기상청 단기예보 요약
  4) 검색(RAG)   : 후보를 임베딩해 벡터DB에 넣고, 여행 취향과 유사한 상위 K개만 추림
  5) 생성        : 후보+이슈+날씨를 Ollama에 주고 추천/리스크/제약사항 JSON 받기
  6) 검증·조립   : LLM이 고른 id를 실제 장소/기사 정보로 되돌려 채움 (없는 장소는 버림)
"""
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta

from config import (
    NEWS_DAYS_BACK,
    TOUR_AREA_ROWS,
    OVERVIEW_ENRICH_LIMIT,
    TOUR_ROWS_PER_TYPE,
    TRAVEL_CANDIDATE_TOP_K,
)
from collectors.tourism import enrich_overviews, get_festivals, get_tourism_info
from collectors.weather import get_short_term_forecast, summarize_daily
from llm.ollama_client import chat_json
from travel.documents import place_to_document
from travel.ldong import resolve_ldong, resolve_sigungu
from travel.places import SIGHT_TYPES, is_indoor
from travel.prompts import RECOMMEND_SYSTEM_PROMPT, build_user_message
from travel.regions import LEGACY_AREA_CODE, SIDO, normalize_region
from travel.risk_scanner import flag_place_issues, scan_regional_risks

FORECAST_DAYS = 3  # 단기예보가 커버하는 대략적인 일수

_store = None
_store_lock = threading.Lock()


def get_store():
    """요청 사이에 임베딩 모델을 다시 로드하지 않도록 메모리 벡터DB를 하나만 만들어 재사용."""
    global _store
    with _store_lock:
        if _store is None:
            from rag.vector_store import VectorStore  # chromadb/torch가 무거워서 필요할 때 import
            _store = VectorStore(collection_name="travel_rag", persist=False)
        return _store


def warm_up() -> None:
    """임베딩 모델을 백그라운드에서 미리 올려둡니다. 첫 일정 요청이 모델 로딩(수 초~십수 초)을 기다리지 않게 하려는 용도."""
    def run():
        try:
            from travel.embeddings import get_ranker
            get_ranker().load()
        except Exception:
            pass  # 실패해도 요청 시점에 다시 시도하고, 그때도 안 되면 키워드 순위로 대체됨

    threading.Thread(target=run, daemon=True, name="warm-up").start()


# ── 입력 처리 ─────────────────────────────────────────────────────────
def _parse_date(v) -> date:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    s = str(v).strip().replace("-", "").replace(".", "").replace("/", "")
    return datetime.strptime(s, "%Y%m%d").date()


# ── 1) 후보 수집 ──────────────────────────────────────────────────────
FOOD_WORDS = ("맛집", "음식", "먹거리", "식당", "먹", "카페", "디저트", "맛있")


def wants_food(text: str) -> bool:
    return any(k in (text or "") for k in FOOD_WORDS)


def _filter_by_sido_addr(places: list[dict], sido: str) -> list[dict]:
    """여러 시도가 같은 법정동 코드를 공유할 때(행정구역 통합), 주소로 해당 시도만 남깁니다."""
    tokens = [sido] + SIDO[sido]["aliases"]
    return [p for p in places if any(t in p["addr"] for t in tokens)]


WANTED_TYPES = {"12", "14", "15", "25", "28", "32", "38", "39"}  # 관광지·문화시설·축제·여행코스·레포츠·숙박·쇼핑·음식점


def _collect_candidates(sido: str, start: date, end: date, include_food: bool, area: str):
    """
    TourAPI에서 후보 장소를 모읍니다. (음식점(39)도 항상 포함: 식사 장소를 실제 가게로 채우기 위해)

    - 세부 지역(area)이 시군구로 해석되면 그 시군구만 한 번에 전부 받습니다. (시군구는 수백 건 규모)
      예전에는 시도 전체에서 최근 수정순 60곳만 받은 뒤 주소로 걸러서, '성남'이면 1곳만 남는 문제가 있었습니다.
    - 해석되지 않으면(명소 이름 등) 시도 단위로 유형별 TOUR_ROWS_PER_TYPE곳을 받아 주소/이름으로 거릅니다.
    - 법정동 코드 조회가 전부 비면 구 방식(areaCode)으로 한 번 더 시도합니다.
    실패 사유는 warnings에 담아 개발자 정보(제약사항)에 보여줍니다.
    """
    warnings: list[str] = []
    code, shared = resolve_ldong(sido)
    places: list[dict] = []
    used_sigungu = False

    if area:
        sigungu = resolve_sigungu(sido, area)
        for name, scode in sigungu:
            try:
                got = get_tourism_info(l_dong_regn_cd=code, l_dong_signgu_cd=scode, num_rows=TOUR_AREA_ROWS)
                places += [p for p in got if p["content_type_id"] in WANTED_TYPES]
            except Exception as e:
                warnings.append(f"관광정보({name}) 조회 실패: {type(e).__name__}: {str(e)[:120]}")
        used_sigungu = bool(places)
        if sigungu and not places:
            warnings.append(f"'{area}' 시군구({', '.join(n for n, _ in sigungu)})에서 장소를 받지 못해 {sido} 전체에서 찾아봤습니다.")

    if not places:
        types = ["12", "14", "28", "39"]

        def fetch(t, **kw):
            return get_tourism_info(content_type_id=t, num_rows=TOUR_ROWS_PER_TYPE, **kw)

        def run_all(**kw):
            got, errs, counts = [], [], {}
            with ThreadPoolExecutor(max_workers=4) as ex:
                futures = {t: ex.submit(fetch, t, **kw) for t in types}
                for t, f in futures.items():
                    try:
                        r = f.result()
                        got += r
                        counts[t] = len(r)
                    except Exception as e:
                        counts[t] = "오류"
                        errs.append(f"관광정보(타입 {t}) 조회 실패: {type(e).__name__}: {str(e)[:120]}")
            return got, errs, counts

        places, errs, counts = run_all(l_dong_regn_cd=code)
        tried = f"lDongRegnCd={code} → {counts}"
        if not places and sido in LEGACY_AREA_CODE:
            legacy, errs2, counts2 = run_all(area_code=LEGACY_AREA_CODE[sido])
            if legacy:
                places = legacy
                errs = []
                warnings.append("법정동 코드 조회 결과가 없어 구 방식(areaCode)으로 조회했습니다.")
            else:
                errs += errs2
                tried += f" / areaCode={LEGACY_AREA_CODE[sido]} → {counts2}"
        warnings += errs[:3]  # 같은 오류가 반복되므로 앞쪽만 노출
        if not places and not errs:
            warnings.append(f"관광정보 조회는 성공했지만 결과가 0건이에요 (타입별 건수: {tried}). python diagnose_api.py 로 확인해 보세요.")

    # 여행 기간과 겹치는 축제/행사
    try:
        s, e_ = start.strftime("%Y%m%d"), end.strftime("%Y%m%d")
        for fest in get_festivals(code, s, e_, num_rows=30):
            fs, fe = fest["event_start"], fest["event_end"] or fest["event_start"]
            if fs and fe and not (fs <= e_ and fe >= s):
                continue  # 기간이 안 겹치면 제외
            places.append(fest)
    except Exception as e:
        warnings.append(f"축제 정보 조회 실패: {type(e).__name__}: {str(e)[:100]}")

    # 중복/빈 제목 제거
    uniq, seen = [], set()
    for p in places:
        key = p["content_id"] or p["title"]
        if not p["title"] or key in seen:
            continue
        seen.add(key)
        p["indoor"] = is_indoor(p)
        uniq.append(p)

    if shared and uniq:
        filtered = _filter_by_sido_addr(uniq, sido)
        if filtered:
            uniq = filtered
        else:
            warnings.append(f"'{sido}' 주소로 걸러낼 수 없어 통합된 지역 전체를 대상으로 했습니다.")

    if area:
        # 시군구 코드로 받은 경우에도 축제는 시도 단위라서 주소로 한 번 더 거른다
        keep = [p for p in uniq if area in p["addr"] or area in p["title"]]
        if used_sigungu:
            uniq = [p for p in uniq if p["content_type_id"] != "15" or p in keep]
        elif keep:
            uniq = keep
        elif uniq:
            warnings.append(f"'{area}'에 해당하는 장소를 찾지 못해 {sido} 전체를 대상으로 추천했습니다.")
    return uniq, warnings


# ── 3) 날씨 ───────────────────────────────────────────────────────────
def _collect_weather(sido: str, start: date, end: date, today: date):
    if end < today or start > today + timedelta(days=FORECAST_DAYS):
        return [], "out_of_range", ""
    try:
        days = summarize_daily(get_short_term_forecast(region=sido))
    except Exception as e:
        return [], "error", f"{type(e).__name__}: {str(e)[:100]}"
    lo, hi = start.isoformat(), end.isoformat()
    days = [d for d in days if lo <= d["date"] <= hi]
    return days, ("ok" if days else "out_of_range"), ""


def _weather_line(d: dict) -> str:
    temp = f"{d['tmin']:.0f}~{d['tmax']:.0f}℃" if d["tmin"] is not None and d["tmax"] is not None else "기온 정보 없음"
    pop = f"{d['pop_max']}%" if d["pop_max"] is not None else "정보없음"
    return f"- {d['date']}: {temp}, 강수확률 최대 {pop}, 하늘 {d['sky']}, 강수 {d['precip']}"


# ── 메인 ──────────────────────────────────────────────────────────────
def recommend_trip(
    region: str,
    start_date,
    end_date,
    preferences: str = "",
    area: str = "",
    party: str = "",
    top_n: int = 5,
    store=None,
    today: date | None = None,
) -> dict:
    """
    여행지 추천 결과를 dict로 돌려줍니다.

    Args:
        region: 시도명 ('부산', '제주', '서울특별시' 등)
        start_date, end_date: 여행 기간 (date 또는 'YYYY-MM-DD')
        preferences: 취향/요청 자유 텍스트 (예: "조용한 바다 산책, 사진 찍기 좋은 곳")
        area: 시군구 등 세부 지역 (예: "해운대", "경주")
        party: 동행 (예: "커플", "아이 동반 가족")
        top_n: 추천 개수
        store: 벡터DB (None이면 get_store() 사용)
        today: 테스트용 오늘 날짜 주입

    Raises:
        ValueError: 지원하지 않는 지역, 날짜 오류
        llm.ollama_client.OllamaConnectionError: Ollama 연결 문제
    """
    sido = normalize_region(region)
    if sido is None:
        raise ValueError(f"지원하지 않는 지역입니다: '{region}'. 가능: {', '.join(SIDO)}")
    start, end = _parse_date(start_date), _parse_date(end_date)
    if end < start:
        raise ValueError("종료일이 시작일보다 빠릅니다.")
    today = today or date.today()
    info = SIDO[sido]
    top_n = max(1, min(int(top_n), 10))
    warnings: list[str] = []

    # 1) 후보
    places, w = _collect_candidates(sido, start, end, wants_food(preferences), area)
    warnings += w

    # 2) 이슈 뉴스 (후보가 없어도 리스크 정보는 의미가 있으므로 먼저 수집)
    news, w = scan_regional_risks(sido, area=area, days_back=NEWS_DAYS_BACK)
    warnings += w
    news_by_id = {n["id"]: n for n in news}

    # 3) 날씨
    weather, wstatus, werr = _collect_weather(sido, start, end, today)
    if wstatus == "error":
        warnings.append(f"날씨 조회 실패로 날씨를 반영하지 못했습니다 ({werr})")

    base = {
        "region": sido,
        "area": area,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "weather": weather,
        "weather_city": info["city"] if weather else "",
    }

    if not places:
        return {
            **base,
            "summary": "조건에 맞는 후보 장소를 가져오지 못했습니다.",
            "recommendations": [],
            "risks": [],
            "caveats": warnings or ["TourAPI에서 후보 장소가 조회되지 않았습니다. 키/엔드포인트를 확인하세요."],
            "used_sources": [],
            "meta": {"candidates": 0, "news_items": len(news)},
        }

    flag_place_issues(places, news)
    warnings += enrich_overviews(places, OVERVIEW_ENRICH_LIMIT)

    # 4) 벡터DB에 넣고 검색
    store = store or get_store()
    request_id = uuid.uuid4().hex[:12]
    place_by_cid = {p["content_id"] or p["title"]: p for p in places}
    docs = [place_to_document(p, sido, request_id) for p in places]
    query = " ".join(x for x in [sido, area, preferences, party] if x) or f"{sido} 대표 관광지"
    try:
        store.add_documents(docs)
        hits = store.search(query, top_k=TRAVEL_CANDIDATE_TOP_K, where={"request_id": request_id})
    finally:
        try:
            store.delete(where={"request_id": request_id})
        except Exception:
            pass

    candidates = []  # [(candidate_id, place)]
    for i, h in enumerate(hits, 1):
        p = place_by_cid.get(h["metadata"].get("content_id", ""))
        if p:
            candidates.append((f"C{i}", p))
    cand_map = dict(candidates)

    # 5) LLM
    def cand_line(cid, p):
        line = f"{cid} | {p['content_type']} | {p['title']} | 주소: {p['addr'] or '정보없음'}"
        if p["overview"]:
            line += f" | 소개: {p['overview'][:150]}"
        if p["event_start"]:
            line += f" | 행사기간: {p['event_start']}~{p['event_end']}"
        if p.get("related_news_ids"):
            titles = "; ".join(f"{nid} {news_by_id[nid]['title'][:40]}" for nid in p["related_news_ids"][:2])
            line += f" | 관련이슈: {titles}"
        return line

    news_lines = [
        f"{n['id']} | [{n['category']}] {n['pub_date']} | {n['title']} | {n['description'][:120]}"
        for n in news
    ]
    user_message = build_user_message(
        sido=sido, area=area, start=start.isoformat(), end=end.isoformat(),
        party=party, preferences=preferences, top_n=top_n,
        candidate_lines=[cand_line(cid, p) for cid, p in candidates],
        news_lines=news_lines,
        weather_lines=[_weather_line(d) for d in weather],
        weather_city=info["city"],
    )
    parsed, raw = chat_json(RECOMMEND_SYSTEM_PROMPT, user_message)

    # 6) 검증 · 조립
    llm_ok = parsed is not None
    parsed = parsed or {}

    def build_rec(cid, reason, risk_note):
        p = cand_map[cid]
        note = (risk_note or "").strip()
        if not note and p.get("related_news_ids"):
            note = "관련 뉴스: " + news_by_id[p["related_news_ids"][0]]["title"]
        return {
            "name": p["title"], "type": p["content_type"], "address": p["addr"],
            "reason": reason, "risk_note": note, "image": p["image"],
            "mapx": p["mapx"], "mapy": p["mapy"], "content_id": p["content_id"],
            "related_news": [news_by_id[n]["link"] for n in p.get("related_news_ids", []) if n in news_by_id],
        }

    recs, used = [], set()
    for r in parsed.get("recommendations", []) if isinstance(parsed.get("recommendations"), list) else []:
        cid = str(r.get("candidate_id", "")).strip() if isinstance(r, dict) else ""
        if cid in cand_map and cid not in used:  # 목록에 없는 id(환각)는 버림
            used.add(cid)
            recs.append(build_rec(cid, str(r.get("reason", "")).strip(), str(r.get("risk_note", ""))))
        if len(recs) >= top_n:
            break
    for i, r in enumerate(recs, 1):
        r["rank"] = i

    if not recs:  # 폴백: 검색 유사도 상위 후보
        warnings.append("AI 응답에서 유효한 추천을 얻지 못해 검색 유사도 상위 후보를 그대로 보여줍니다.")
        for i, (cid, _) in enumerate(candidates[:top_n], 1):
            rec = build_rec(cid, "여행 취향과 검색 유사도가 높은 후보입니다.", "")
            rec["rank"] = i
            recs.append(rec)

    risks = []
    raw_risks = parsed.get("risks", []) if isinstance(parsed.get("risks"), list) else []
    for r in raw_risks:
        nid = str(r.get("news_id", "")).strip() if isinstance(r, dict) else ""
        if nid in news_by_id:
            n = news_by_id[nid]
            level = str(r.get("level", "medium")).lower()
            risks.append({
                "level": level if level in ("high", "medium", "low") else "medium",
                "category": n["category"], "title": n["title"],
                "detail": str(r.get("detail", "")).strip(),
                "link": n["link"], "pub_date": n["pub_date"],
            })
    if not llm_ok and news:  # LLM 실패 시 기사 자체를 노출
        risks = [{"level": "medium", "category": n["category"], "title": n["title"],
                  "detail": "관련 기사입니다. 내용을 확인하세요.", "link": n["link"], "pub_date": n["pub_date"]}
                 for n in news[:3]]

    # 결정적으로 만들 수 있는 제약사항은 코드에서 직접 추가 (모델 성능과 무관하게 항상 표시)
    caveats = list(warnings)
    caveats.append(f"뉴스 이슈는 최근 {NEWS_DAYS_BACK}일 기사 기준이라 여행일이 멀면 상황이 달라질 수 있습니다.")
    if wstatus == "out_of_range":
        caveats.append(f"여행일이 단기예보 제공 범위(오늘부터 약 {FORECAST_DAYS}일) 밖이라 날씨는 반영하지 못했습니다.")
    elif weather:
        caveats.append(f"날씨는 {info['city']} 기준 예보라 세부 지역과 다를 수 있습니다.")
    caveats.append("관광정보는 한국관광공사 TourAPI 기준이며 실제 운영시간·휴무는 방문 전 확인이 필요합니다.")
    for c in parsed.get("caveats", []) if isinstance(parsed.get("caveats"), list) else []:
        if isinstance(c, str) and c.strip() and c.strip() not in caveats:
            caveats.append(c.strip())

    used_sources = ["tourism"]
    if news:
        used_sources.append("naver_news")
    if weather:
        used_sources.append("weather")

    return {
        **base,
        "summary": str(parsed.get("summary", "")).strip() or f"{sido} 여행 후보를 취향 유사도 순으로 정리했습니다.",
        "recommendations": recs,
        "risks": risks,
        "caveats": caveats,
        "used_sources": used_sources,
        "meta": {"candidates": len(places), "retrieved": len(candidates), "news_items": len(news), "llm_json_ok": llm_ok},
    }


def _collect_type(sido: str, area: str, ctype: str) -> tuple[list[dict], list[str]]:
    """한 유형(예: 32 숙박, 25 여행코스)만 모은다. 시군구로 해석되면 그 시군구에서, 아니면 시도 단위로 받아 주소로 거른다."""
    warnings: list[str] = []
    code, _shared = resolve_ldong(sido)
    places: list[dict] = []
    if area:
        for name, scode in resolve_sigungu(sido, area):
            try:
                places += get_tourism_info(l_dong_regn_cd=code, l_dong_signgu_cd=scode, content_type_id=ctype, num_rows=TOUR_AREA_ROWS)
            except Exception as e:
                warnings.append(f"관광정보({name}, 유형 {ctype}) 조회 실패: {type(e).__name__}: {str(e)[:100]}")
    if not places:
        try:
            places = get_tourism_info(l_dong_regn_cd=code, content_type_id=ctype, num_rows=TOUR_ROWS_PER_TYPE)
        except Exception as e:
            warnings.append(f"관광정보(유형 {ctype}) 조회 실패: {type(e).__name__}: {str(e)[:100]}")
        if area:
            places = [p for p in places if area in p["addr"] or area in p["title"]] or places
    for p in places:
        p["indoor"] = is_indoor(p)
    return places, warnings


def _collect_festivals(sido: str, area: str, start: date, end: date) -> tuple[list[dict], list[str]]:
    """기간(start~end)과 겹치는 행사·축제·공연."""
    warnings: list[str] = []
    code, _shared = resolve_ldong(sido)
    out: list[dict] = []
    try:
        s_, e_ = start.strftime("%Y%m%d"), end.strftime("%Y%m%d")
        for fest in get_festivals(code, s_, e_, num_rows=60):
            fs, fe = fest["event_start"], fest["event_end"] or fest["event_start"]
            if fs and fe and not (fs <= e_ and fe >= s_):
                continue
            fest["indoor"] = is_indoor(fest)
            out.append(fest)
    except Exception as e:
        warnings.append(f"축제 정보 조회 실패: {type(e).__name__}: {str(e)[:100]}")
    if area:
        out = [p for p in out if area in p["addr"] or area in p["title"]]
    return out, warnings
