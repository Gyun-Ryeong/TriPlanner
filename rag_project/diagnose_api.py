"""
API 진단 도구 - "키 문제인지, API 문제인지" 를 구분해서 알려줍니다.

실행:
    python diagnose_api.py            # 전체
    python diagnose_api.py tour       # 관광정보만
    python diagnose_api.py weather    # 기상청만
    python diagnose_api.py air        # 에어코리아만
    python diagnose_api.py naver      # 네이버만
    python diagnose_api.py ollama     # Ollama 연결만

프로젝트의 다른 코드를 거치지 않고 API를 직접 호출해서, 서버가 돌려준 원문과 판정을 그대로 보여줍니다.
(인증키는 앞 4자리만 보이도록 가려서 출력합니다)
"""
import json
import sys
from datetime import datetime, timedelta
from urllib.parse import unquote

import requests

from config import ENDPOINTS, NAVER_CLIENT_ID, NAVER_CLIENT_SECRET, PUBLIC_DATA_API_KEY

TIMEOUT = 20
RESULTS: list[tuple[str, bool, str]] = []

# 서버가 돌려주는 대표 오류 문구 → 의미와 해결 방법
KNOWN_ERRORS = [
    ("SERVICE_KEY_IS_NOT_REGISTERED", "등록되지 않은 인증키입니다. 키를 잘못 복사했거나, 활용신청 승인/동기화가 아직 안 됐을 수 있어요(보통 수 분~수 시간)."),
    ("SERVICE ACCESS DENIED", "이 서비스에 대한 접근 권한이 없습니다. 이 API의 '활용신청'을 하지 않았거나 승인 대기 중이에요."),
    ("SERVICE_ACCESS_DENIED", "이 서비스에 대한 접근 권한이 없습니다. 이 API의 '활용신청'을 하지 않았거나 승인 대기 중이에요."),
    ("LIMITED_NUMBER_OF_SERVICE_REQUESTS", "일일 호출 한도를 초과했습니다. 내일 다시 시도하거나 운영계정 전환을 신청하세요."),
    ("DEADLINE_HAS_EXPIRED", "인증키 사용 기간이 만료되었습니다. 활용기간 연장이 필요해요."),
    ("UNREGISTERED_IP", "허용되지 않은 IP입니다. 활용신청에 IP 제한이 걸려 있는지 확인하세요."),
    ("NO_OPENAPI_SERVICE_ERROR", "요청한 서비스 주소가 없습니다. 엔드포인트 URL이 틀렸거나 서비스가 종료되었을 수 있어요."),
    ("INVALID_REQUEST_PARAMETER", "요청 파라미터 오류입니다. 필수 파라미터 누락 또는 형식 오류예요."),
    ("APPLICATION_ERROR", "서비스 제공기관 내부 오류입니다. 잠시 뒤 다시 시도해보세요."),
    ("HTTP_ERROR", "서비스 제공기관 서버 오류입니다."),
    ("Unexpected errors", "서버 내부 오류입니다. 파라미터 조합이 지원되지 않을 때도 이렇게 나와요."),
]


def mask_key(text: str) -> str:
    key = unquote(PUBLIC_DATA_API_KEY.strip())
    if key and len(key) > 8:
        text = text.replace(key, key[:4] + "…(가림)")
    enc = PUBLIC_DATA_API_KEY.strip()
    if enc and len(enc) > 8:
        text = text.replace(enc, enc[:4] + "…(가림)")
    return text


def check_key_shape() -> list[str]:
    """.env에 키를 넣을 때 흔한 실수를 먼저 점검."""
    notes = []
    raw = PUBLIC_DATA_API_KEY
    if not raw:
        return ["PUBLIC_DATA_API_KEY가 비어 있습니다. .env에 키를 넣고 저장(Ctrl+S)했는지, .env가 프로젝트 폴더 바로 아래에 있는지 확인하세요."]
    if raw != raw.strip():
        notes.append("키 앞뒤에 공백이 있습니다.")
    if any(c in raw for c in "\"'"):
        notes.append("키에 따옴표가 들어 있습니다. 따옴표 없이 값만 넣으세요.")
    if len(raw.strip()) < 20:
        notes.append(f"키 길이가 {len(raw.strip())}자로 너무 짧습니다. 일부만 복사했을 수 있어요.")
    kind = "Encoding 키(%2B 등 포함)" if "%" in raw else "Decoding 키"
    notes.append(f"키 길이 {len(raw.strip())}자, {kind} 형태입니다. (둘 다 사용 가능하도록 처리돼 있어요)")
    return notes


def judge(resp: requests.Response) -> tuple[bool, str, str]:
    """(성공 여부, 한 줄 판정, 건수/요약)"""
    body = resp.text.strip()
    if resp.status_code in (401, 403):
        return False, "인증 실패(HTTP %d). 키 오류이거나 해당 서비스 권한이 없어요." % resp.status_code, ""
    if resp.status_code == 404:
        return False, "HTTP 404: 엔드포인트 URL이 틀렸습니다.", ""
    if resp.status_code >= 500:
        return False, f"HTTP {resp.status_code}: 제공기관 서버 오류입니다.", ""
    for needle, meaning in KNOWN_ERRORS:
        if needle.lower() in body.lower():
            return False, meaning, ""

    try:
        data = resp.json()
    except ValueError:
        # XML 형식으로 온 경우: 간단히 resultCode만 확인
        if "<resultCode>00" in body or "<resultCode>0000" in body:
            return True, "정상(XML 응답)", ""
        return False, "JSON이 아닌 응답입니다. 원문을 확인하세요.", ""

    header = (data.get("response") or {}).get("header") or {}
    code = str(header.get("resultCode", "")).strip()
    msg = str(header.get("resultMsg", "")).strip()
    if code and code not in ("00", "0000"):
        if "NODATA" in msg.upper().replace("_", "").replace(" ", ""):
            return True, "정상(조회 결과 0건)", "0건"
        return False, f"API 오류 응답: code={code}, msg={msg}", ""

    body_obj = (data.get("response") or {}).get("body") or {}
    total = body_obj.get("totalCount")
    items = body_obj.get("items")
    if isinstance(items, dict):
        items = items.get("item", [])
    if isinstance(items, dict):
        items = [items]
    n = len(items) if isinstance(items, list) else 0
    return True, "정상", f"totalCount={total}, 이번 응답 {n}건"


def run(name: str, url: str, params: dict, show_items=None, headers: dict | None = None,
        timeout: int = TIMEOUT) -> requests.Response | None:
    print(f"\n[{name}]")
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=timeout)
    except requests.exceptions.Timeout as e:
        print(f"  ✗ 시간 초과: {timeout}초 안에 응답이 오지 않았어요.")
        print("    → 키/권한 문제가 아니라 '서버가 느린' 경우예요. 위에서 같은 사이트(apis.data.go.kr)의 다른 API가 PASS였다면")
        print("      네트워크 문제도 아닙니다. 에어코리아 서버는 가끔 느려져요. 잠시 뒤 이 명령을 다시 실행해 보세요.")
        RESULTS.append((name, False, "시간 초과(서버 지연) - 잠시 뒤 재시도"))
        return None
    except requests.exceptions.RequestException as e:
        print(f"  ✗ 연결 실패: {type(e).__name__}: {mask_key(str(e))[:200]}")
        print("    → 인터넷 연결, 방화벽, 프록시를 확인하세요.")
        RESULTS.append((name, False, "연결 실패"))
        return None

    print(f"  요청: {mask_key(resp.url)[:230]}")
    print(f"  HTTP {resp.status_code} / {resp.headers.get('Content-Type', '')}")
    ok, verdict, summary = judge(resp)
    print(f"  {'✓' if ok else '✗'} {verdict}" + (f" ({summary})" if summary else ""))
    if not ok:
        print(f"  서버 응답 원문: {mask_key(resp.text.strip())[:300]}")
    elif show_items:
        try:
            show_items(resp.json())
        except Exception:
            pass
    RESULTS.append((name, ok, verdict))
    return resp


def _items(data: dict) -> list:
    items = ((data.get("response") or {}).get("body") or {}).get("items")
    if isinstance(items, dict):
        items = items.get("item", [])
    if isinstance(items, dict):
        items = [items]
    return items if isinstance(items, list) else []


def _key() -> str:
    return unquote(PUBLIC_DATA_API_KEY.strip())


# ── 관광정보 ─────────────────────────────────────────────────────────
def diag_tour() -> None:
    print("\n=== 한국관광공사 국문 관광정보 서비스 (KorService2) ===")
    app = {"MobileOS": "ETC", "MobileApp": "TriPlanner", "_type": "json"}

    found = {}

    def show_ldong(data):
        items = _items(data)
        names = []
        for it in items[:20]:
            low = {k.lower(): v for k, v in it.items()}
            code = low.get("code") or low.get("ldongregncd") or ""
            name = low.get("name") or low.get("ldongregnnm") or ""
            names.append(f"{code}:{name}")
            if name:
                found[name] = code
        print("  시도 코드 목록:", ", ".join(names))
        print("  (이 코드는 '법정동 시도 코드'이며, 행정구역 개편이 있으면 값이 바뀔 수 있어요)")

    run("관광정보 ① 법정동 코드 목록(ldongCode2) - 인증/활용신청 확인용", ENDPOINTS["tour_ldong"],
        {"serviceKey": _key(), "numOfRows": 50, "pageNo": 1, **app}, show_ldong)

    code = next((c for n, c in found.items() if "부산" in n), "26")

    def show_places(data):
        for it in _items(data)[:3]:
            print(f"    - {it.get('title')} / {it.get('addr1')}")

    r = run(f"관광정보 ② 지역 관광지 목록(areaBasedList2, lDongRegnCd={code}) - 부산", ENDPOINTS["tourism"],
            {"serviceKey": _key(), "numOfRows": 3, "pageNo": 1, "arrange": "C", "contentTypeId": 12,
             "lDongRegnCd": code, **app}, show_places)

    if r is not None and not RESULTS[-1][1]:
        run("관광정보 ③ (비교) 옛 방식 areaCode=6", ENDPOINTS["tourism"],
            {"serviceKey": _key(), "numOfRows": 3, "pageNo": 1, "arrange": "C", "contentTypeId": 12,
             "areaCode": 6, **app}, show_places)

    # 진단은 위에서 직접 호출하지만, 앱은 collectors 코드를 거칩니다. 둘의 결과가 다르면 앱 쪽 요청 파라미터 문제예요.
    print("\n[관광정보 ⑤ 앱 코드 경로(collectors.tourism.get_tourism_info) - ②와 결과가 다르면 앱 쪽 문제]")
    try:
        from collectors.tourism import get_tourism_info
        got = get_tourism_info(l_dong_regn_cd=code, content_type_id="12", num_rows=3)
        print(f"  {'✓' if got else '✗'} {len(got)}건" + (f" (예: {got[0]['title']})" if got else ""))
        RESULTS.append(("관광정보 ⑤ 앱 코드 경로", bool(got), "정상" if got else "0건"))
    except Exception as e:
        print(f"  ✗ {type(e).__name__}: {str(e)[:250]}")
        RESULTS.append(("관광정보 ⑤ 앱 코드 경로", False, f"{type(e).__name__}: {str(e)[:120]}"))

    # ⑥ 시군구 코드 조회 + 성남 전체 조회 (세부 지역 일정이 후보를 충분히 받는지)
    sg = {}

    def show_sg(data):
        for it in _items(data):
            low = {k.lower(): v for k, v in it.items()}
            c = low.get("code") or low.get("ldongsigngucd") or ""
            n = low.get("name") or low.get("ldongsigngunm") or ""
            if c and n:
                sg[n] = c
        print(f"  시군구 {len(sg)}개: " + ", ".join(f"{c}:{n}" for n, c in list(sg.items())[:12]) + (" ..." if len(sg) > 12 else ""))
        print("  '성남' 해당:", {n: c for n, c in sg.items() if "성남" in n} or "없음")

    run("관광정보 ⑥ 시군구 코드 목록(ldongCode2, lDongRegnCd=41 경기)", ENDPOINTS["tour_ldong"],
        {"serviceKey": _key(), "numOfRows": 300, "pageNo": 1, "lDongRegnCd": 41, **app}, show_sg)

    seongnam = [c for n, c in sg.items() if "성남" in n]
    if seongnam:
        def show_all(data):
            from collections import Counter
            cnt = Counter(str(i.get("contenttypeid")) for i in _items(data))
            print(f"    유형별 건수(이번 응답): {dict(cnt)}  (12=관광지 14=문화시설 28=레포츠 39=음식점)")

        run(f"관광정보 ⑦ 성남 시군구 전체(areaBasedList2, lDongRegnCd=41&lDongSignguCd={seongnam[0]}, 유형 구분 없이)", ENDPOINTS["tourism"],
            {"serviceKey": _key(), "numOfRows": 1000, "pageNo": 1, "arrange": "C", "lDongRegnCd": 41,
             "lDongSignguCd": seongnam[0], **app}, show_all)

    # ⑧ 음식점 소개 정보 (맛집 답변의 대표메뉴·영업시간·주차)
    rest = {}

    def pick_restaurants(data):
        for it in _items(data)[:3]:
            rest[str(it.get("contentid"))] = it.get("title")
        print("    음식점 예:", ", ".join(rest.values()))

    run("관광정보 ⑧-a 부산 음식점 목록(areaBasedList2, contentTypeId=39)", ENDPOINTS["tourism"],
        {"serviceKey": _key(), "numOfRows": 3, "pageNo": 1, "arrange": "C", "contentTypeId": 39, "lDongRegnCd": 26, **app}, pick_restaurants)

    def show_intro(data):
        for it in _items(data)[:1]:
            keys = ["firstmenu", "treatmenu", "opentimefood", "restdatefood", "parkingfood"]
            print("    " + " / ".join(f"{k}={str(it.get(k))[:25]!r}" for k in keys))

    for cid in list(rest)[:2]:
        run(f"관광정보 ⑧-b 음식점 소개 정보(detailIntro2, contentId={cid})", ENDPOINTS["tour_intro"],
            {"serviceKey": _key(), "contentId": cid, "contentTypeId": 39, "numOfRows": 1, "pageNo": 1, **app}, show_intro)

    # ⑨ 장소 이름 검색 (특정 장소 문의: "OO 정보 알려줘")
    found = {}

    def show_search(data):
        for it in _items(data)[:3]:
            found[str(it.get("contentid"))] = (it.get("title"), it.get("contenttypeid"))
            print(f"    - {it.get('title')} / {it.get('addr1')} (유형 {it.get('contenttypeid')})")

    run("관광정보 ⑨-a 장소 이름 검색(searchKeyword2, keyword=해운대해수욕장)", ENDPOINTS["tour_search"],
        {"serviceKey": _key(), "keyword": "해운대해수욕장", "numOfRows": 5, "pageNo": 1, "arrange": "A", **app}, show_search)

    def show_hours(data):
        for it in _items(data)[:1]:
            keys = [k for k in it if any(w in k for w in ("usetime", "restdate", "opentime", "parking", "infocenter"))]
            print("    운영 관련 필드:", {k: str(it[k])[:30] for k in keys})

    for cid, (title, ctype) in list(found.items())[:1]:
        run(f"관광정보 ⑨-b 운영 정보(detailIntro2, {title}, 유형 {ctype})", ENDPOINTS["tour_intro"],
            {"serviceKey": _key(), "contentId": cid, "contentTypeId": ctype, "numOfRows": 1, "pageNo": 1, **app}, show_hours)

    # ⑩ 숙박(32) · 추천 여행코스(25) · 축제(15)
    def show_types(data):
        for it in _items(data)[:2]:
            print(f"    - {it.get('title')} / {it.get('addr1') or '(주소 없음)'} (유형 {it.get('contenttypeid')})")

    for ctype, label in ((32, "숙박"), (25, "추천 여행코스")):
        run(f"관광정보 ⑩ {label} 목록(areaBasedList2, contentTypeId={ctype}, 부산)", ENDPOINTS["tourism"],
            {"serviceKey": _key(), "numOfRows": 3, "pageNo": 1, "arrange": "C", "contentTypeId": ctype, "lDongRegnCd": 26, **app}, show_types)
    today_s = datetime.now().strftime("%Y%m%d")
    run("관광정보 ⑩ 축제·행사(searchFestival2, 오늘 이후, 부산)", ENDPOINTS["tour_festival"],
        {"serviceKey": _key(), "numOfRows": 3, "pageNo": 1, "arrange": "C", "eventStartDate": today_s, "lDongRegnCd": 26, **app}, show_types)

    def show_detail(data):
        for it in _items(data)[:1]:
            print(f"    - {it.get('title')}: {(it.get('overview') or '')[:60]}")

    run("관광정보 ④ 장소 소개글(detailCommon2)", ENDPOINTS["tour_detail"],
        {"serviceKey": _key(), "contentId": 126508, "numOfRows": 1, "pageNo": 1, **app}, show_detail)


# ── 기상청 ───────────────────────────────────────────────────────────
def diag_weather() -> None:
    print("\n=== 기상청 단기예보 조회서비스 ===")
    now = datetime.now() - timedelta(minutes=15)
    hours = [h for h in (2, 5, 8, 11, 14, 17, 20, 23) if h <= now.hour]
    if hours:
        base_date, base_time = now.strftime("%Y%m%d"), f"{max(hours):02d}00"
    else:
        base_date, base_time = (now - timedelta(days=1)).strftime("%Y%m%d"), "2300"

    def show(data):
        cats = sorted({i.get("category") for i in _items(data)})
        print(f"    예보 항목: {', '.join(c for c in cats if c)}")

    run(f"기상청 단기예보(getVilageFcst, 서울 격자 60/127, 발표 {base_date} {base_time})", ENDPOINTS["weather"],
        {"serviceKey": _key(), "numOfRows": 300, "pageNo": 1, "dataType": "JSON",
         "base_date": base_date, "base_time": base_time, "nx": 60, "ny": 127}, show)


# ── 에어코리아 ───────────────────────────────────────────────────────
def diag_air() -> None:
    print("\n=== 에어코리아 대기오염정보 ===")
    print("  ※ data.go.kr에서 '한국환경공단_에어코리아_대기오염정보'를 활용신청해야 아래 두 API가 모두 동작합니다.")
    today = datetime.now().strftime("%Y-%m-%d")

    def show_fc(data):
        for it in _items(data)[:1]:
            print(f"    - {it.get('dataTime')} / 대상일 {it.get('informData')} / {str(it.get('informGrade'))[:60]}")

    run("에어코리아 ① 미세먼지 예보통보(getMinuDustFrcstDspth, PM10)", ENDPOINTS["air_forecast"],
        {"serviceKey": _key(), "returnType": "json", "numOfRows": 10, "pageNo": 1,
         "searchDate": today, "informCode": "PM10"}, show_fc, timeout=60)

    def show_rt(data):
        for it in _items(data)[:2]:
            print(f"    - {it.get('stationName')}: PM10 {it.get('pm10Value')}, PM2.5 {it.get('pm25Value')} ({it.get('dataTime')})")

    run("에어코리아 ② 시도별 실시간 측정값(getCtprvnRltmMesureDnsty, 서울)", ENDPOINTS["air_quality"],
        {"serviceKey": _key(), "returnType": "json", "numOfRows": 5, "pageNo": 1,
         "sidoName": "서울", "ver": "1.3"}, show_rt, timeout=60)


# ── 네이버 (NAVER API HUB) ───────────────────────────────────────────
def diag_naver() -> None:
    print("\n=== 네이버 뉴스 검색 (NAVER API HUB) ===")
    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
        print("  ✗ NAVER_CLIENT_ID / NAVER_CLIENT_SECRET이 비어 있습니다. .env를 확인하세요.")
        RESULTS.append(("네이버 뉴스", False, "키 없음"))
        return
    print(f"  읽은 값: ID 길이 {len(NAVER_CLIENT_ID)}자, Secret 길이 {len(NAVER_CLIENT_SECRET)}자")
    headers = {"X-NCP-APIGW-API-KEY-ID": NAVER_CLIENT_ID, "X-NCP-APIGW-API-KEY": NAVER_CLIENT_SECRET}
    print(f"\n[뉴스 검색 {ENDPOINTS['naver_news_hub']}]")
    try:
        r = requests.get(ENDPOINTS["naver_news_hub"], headers=headers, params={"query": "부산 날씨", "display": 2}, timeout=TIMEOUT)
    except requests.exceptions.RequestException as e:
        print(f"  ✗ 연결 실패: {type(e).__name__}")
        RESULTS.append(("네이버 뉴스", False, "연결 실패"))
        return
    if r.status_code == 200:
        print(f"  ✓ 정상 ({len(r.json().get('items', []))}건)")
        RESULTS.append(("네이버 뉴스", True, "정상"))
        return

    print(f"  ✗ HTTP {r.status_code}: {r.text.strip()[:250]}")
    hints = {
        401: "인증 실패",
        403: "권한 없음",
        429: "호출이 너무 몰렸어요. 잠시 뒤 다시 시도하세요 (앱은 자동으로 간격을 두고 재시도합니다)",
    }
    print(f"  → {hints.get(r.status_code, '서버 응답 원문을 확인하세요')}")
    if r.status_code in (401, 403):
        print("  확인할 것:")
        print("   1) 콘솔 NAVER API HUB > Application > 해당 앱의 [인증 정보]의 Client ID/Secret을 그대로 넣었는지 (서로 바뀌지 않았는지)")
        print("   2) 해당 Application의 API 목록에 '뉴스'가 등록돼 있는지")
        print("   3) 값 앞뒤 공백/따옴표 없이 저장(Ctrl+S) 했는지, Secret을 재발급했다면 새 값으로 바꿨는지")
    RESULTS.append(("네이버 뉴스", False, hints.get(r.status_code, f"HTTP {r.status_code}")))


# ── Ollama ───────────────────────────────────────────────────────────
def diag_ollama() -> None:
    from config import OLLAMA_BASE_URL, OLLAMA_MODEL
    print("\n=== Ollama ===")
    print(f"  .env의 OLLAMA_BASE_URL = {OLLAMA_BASE_URL}  /  OLLAMA_MODEL = {OLLAMA_MODEL}")
    bases = [OLLAMA_BASE_URL] + [u for u in ("http://localhost:11434", "http://127.0.0.1:11434") if u != OLLAMA_BASE_URL]
    reachable = None
    for base in bases:
        try:
            r = requests.get(base + "/api/tags", timeout=5)
            r.raise_for_status()
            names = [m["name"] for m in r.json().get("models", [])]
            print(f"  ✓ {base} 응답함. 설치된 모델: {names}")
            reachable = (base, names)
            break
        except Exception as e:
            print(f"  ✗ {base} 연결 실패 ({type(e).__name__})")
    if reachable is None:
        print("  → Ollama에 연결되지 않았어요. 확인할 것:")
        print("    1) Ollama가 켜져 있는지 (트레이 아이콘, 또는 새 터미널에서 `ollama serve`)")
        print("    2) 이 PC의 IP가 바뀌지 않았는지 (`ipconfig`의 IPv4 주소). 공유기 환경에서는 IP가 가끔 바뀝니다.")
        print("    3) 같은 PC에서 돌린다면 .env를 OLLAMA_BASE_URL=http://localhost:11434 로 바꿔보세요.")
        RESULTS.append(("Ollama 연결", False, "연결 안 됨"))
        return
    base, names = reachable
    if base != OLLAMA_BASE_URL:
        print(f"  → .env의 주소({OLLAMA_BASE_URL})는 안 되고 {base} 는 됩니다. .env를 OLLAMA_BASE_URL={base} 로 바꾸세요.")
        RESULTS.append(("Ollama 연결", False, f".env 주소가 틀림 → {base} 사용"))
        return
    if OLLAMA_MODEL not in names:
        print(f"  → OLLAMA_MODEL='{OLLAMA_MODEL}' 이(가) 설치 목록에 없습니다. .env의 모델명을 위 목록과 똑같이 맞추세요.")
        RESULTS.append(("Ollama 모델명", False, "모델명 불일치"))
        return
    RESULTS.append(("Ollama 연결", True, "정상"))


STEPS = {"tour": diag_tour, "weather": diag_weather, "air": diag_air, "naver": diag_naver, "ollama": diag_ollama}


def main() -> None:
    print("=== 인증키 형태 점검 ===")
    for n in check_key_shape():
        print("  -", n)

    targets = sys.argv[1:] or list(STEPS)
    for t in targets:
        if t not in STEPS:
            print(f"알 수 없는 단계: {t} (가능: {', '.join(STEPS)})")
            continue
        STEPS[t]()

    print("\n=== 요약 ===")
    for name, ok, verdict in RESULTS:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}" + ("" if ok else f"\n        → {verdict}"))
    if any(not ok for _, ok, _ in RESULTS):
        print("\nFAIL이 있으면 위 '서버 응답 원문'과 → 판정을 복사해서 알려주세요.")


if __name__ == "__main__":
    main()
