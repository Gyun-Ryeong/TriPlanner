"""
한국환경공단_에어코리아_대기오염정보 (ArpltnInforInqireSvc)

- getMinuDustFrcstDspth     : 미세먼지(PM10)/초미세먼지(PM25) 예보통보 → 오늘~모레 일자별 등급
- getCtprvnRltmMesureDnsty  : 시도별 실시간 측정값 → 지금 상태

※ data.go.kr에서 '한국환경공단_에어코리아_대기오염정보' 활용신청이 필요합니다.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

from config import ENDPOINTS
from collectors.base_client import call_public_api, extract_items
from collectors.cache import ttl_cache

_JSON = {"returnType": "json"}  # 에어코리아는 returnType=json 으로 JSON 응답을 받음

GRADE_ORDER = {"좋음": 1, "보통": 2, "나쁨": 3, "매우나쁨": 4}
GRADE_BY_NUM = {"1": "좋음", "2": "보통", "3": "나쁨", "4": "매우나쁨"}

# 시도 → 예보통보에서 쓰는 권역 이름 (경기/강원은 둘로 나뉘어 있음)
FORECAST_REGION_KEYS = {"경기": ["경기북부", "경기남부"], "강원": ["강원영서", "강원영동"]}


def classify_pm10(value: float) -> str:
    """PM10(㎍/㎥) → 좋음 0~30, 보통 31~80, 나쁨 81~150, 매우나쁨 151~"""
    return "좋음" if value <= 30 else "보통" if value <= 80 else "나쁨" if value <= 150 else "매우나쁨"


def classify_pm25(value: float) -> str:
    """PM2.5(㎍/㎥) → 좋음 0~15, 보통 16~35, 나쁨 36~75, 매우나쁨 76~"""
    return "좋음" if value <= 15 else "보통" if value <= 35 else "나쁨" if value <= 75 else "매우나쁨"


def worst_grade(grades: list[str]) -> str:
    return max(grades, key=lambda g: GRADE_ORDER.get(g, 0))


def parse_inform_grade(text: str) -> dict[str, str]:
    """'서울 : 좋음,제주 : 보통,...' → {'서울': '좋음', '제주': '보통'}"""
    out: dict[str, str] = {}
    for part in (text or "").split(","):
        if ":" not in part:
            continue
        region, grade = part.split(":", 1)
        region, grade = region.strip(), grade.strip().replace(" ", "")
        if region and grade in GRADE_ORDER:
            out[region] = grade
    return out


# ── 예보통보 ──────────────────────────────────────────────────────────
@ttl_cache("air_forecast", 1800, stale_ttl=18 * 3600, fail_cooldown=300)
def get_air_forecast(search_date: str, inform_code: str) -> list[dict]:
    """
    Args:
        search_date: 'YYYY-MM-DD' 발표일
        inform_code: 'PM10' | 'PM25' | 'O3'
    """
    params = {
        "searchDate": search_date,
        "informCode": inform_code,
        "numOfRows": 100,
        "pageNo": 1,
        "returnType": "json",
    }
    parsed = call_public_api(ENDPOINTS["air_forecast"], params, json_params=_JSON, timeout=25, retries=0)
    return extract_items(parsed)


def forecast_by_date(items: list[dict], sido: str) -> dict[str, str]:
    """
    예보통보 항목들에서 해당 시도의 일자별 등급을 뽑습니다.
    같은 날짜에 대한 발표가 여러 번(05/11/17/23시) 있으면 가장 늦은 발표를 사용합니다.
    """
    keys = FORECAST_REGION_KEYS.get(sido, [sido])
    out: dict[str, str] = {}
    for it in sorted(items, key=lambda i: str(i.get("dataTime", "")), reverse=True):
        d = str(it.get("informData", ""))[:10]
        if not d or d in out:
            continue
        grades = parse_inform_grade(str(it.get("informGrade", "")))
        found = [grades[k] for k in keys if k in grades]
        if found:
            out[d] = worst_grade(found)
    return out


# ── 실시간 ────────────────────────────────────────────────────────────
@ttl_cache("air_realtime", 600, stale_ttl=3 * 3600, fail_cooldown=300)
def get_air_quality(sido_name: str = "서울") -> list[dict]:
    """
    시도별 실시간 대기질 측정정보를 조회합니다.

    Args:
        sido_name: 시도명 (서울, 부산, 대구, 인천, 광주, 대전, 울산,
                   경기, 강원, 충북, 충남, 전북, 전남, 경북, 경남, 제주, 세종)
    """
    params = {
        "sidoName": sido_name,
        "numOfRows": 100,
        "pageNo": 1,
        "ver": "1.3",
        "returnType": "json",
    }

    parsed = call_public_api(ENDPOINTS["air_quality"], params, json_params=_JSON, timeout=25, retries=0)
    items = extract_items(parsed)

    results = []
    for item in items:
        results.append({
            "source": "air_quality",
            "station": item.get("stationName", ""),
            "sido": sido_name,
            "pm10": item.get("pm10Value", ""),
            "pm25": item.get("pm25Value", ""),
            "cai_grade": item.get("khaiGrade", ""),  # 1=좋음 2=보통 3=나쁨 4=매우나쁨
            "data_time": item.get("dataTime", ""),
            "raw": item,
        })
    return results


def _num(v) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None  # '-' 또는 점검중


def summarize_realtime(items: list[dict]) -> dict | None:
    """측정소별 값을 시도 평균으로 요약하고 등급을 계산합니다. 유효한 값이 없으면 None."""
    pm10 = [x for x in (_num(i.get("pm10")) for i in items) if x is not None]
    pm25 = [x for x in (_num(i.get("pm25")) for i in items) if x is not None]
    if not pm10 and not pm25:
        return None
    avg10 = sum(pm10) / len(pm10) if pm10 else None
    avg25 = sum(pm25) / len(pm25) if pm25 else None
    return {
        "pm10_value": round(avg10) if avg10 is not None else None,
        "pm25_value": round(avg25) if avg25 is not None else None,
        "pm10_grade": classify_pm10(avg10) if avg10 is not None else None,
        "pm25_grade": classify_pm25(avg25) if avg25 is not None else None,
        "stations": max(len(pm10), len(pm25)),
        "time": next((i.get("data_time") for i in items if i.get("data_time")), ""),
    }


# ── 여행 일정용 요약 ──────────────────────────────────────────────────
def get_air_summary(sido: str, start: date, end: date, today: date | None = None) -> dict:
    """
    여행 기간의 미세먼지 정보를 모읍니다. (예보 PM10·PM25와 실시간 측정을 동시에 호출해 기다리는 시간을 줄입니다)

    Returns:
        {"by_date": {"2026-10-10": {"pm10": "보통", "pm25": "나쁨", "source": "예보"|"실측"}},
         "realtime": {...}|None, "warnings": [...]}
    - 예보통보는 오늘~모레 3일치만 제공됩니다. 그 밖의 날짜는 by_date에 없습니다.
    - 여행 기간에 오늘이 포함되면 실시간 측정값도 함께 조회합니다.
    """
    today = today or date.today()
    warnings: list[str] = []
    by_date: dict[str, dict] = {}
    realtime = None
    lo, hi = start.isoformat(), end.isoformat()

    need_forecast = end >= today and start <= today + timedelta(days=2)
    need_realtime = start <= today <= end
    grades: dict[str, dict] = {}
    failed = 0

    def collect_forecast(ex, search_date: date):
        """해당 발표일의 PM10/PM25 예보를 동시에 불러 grades에 채운다. (실패 건수 반환)"""
        futs = {code: ex.submit(get_air_forecast, search_date.isoformat(), code) for code in ("PM10", "PM25")}
        bad = 0
        for code, f in futs.items():
            try:
                for d, g in forecast_by_date(f.result(), sido).items():
                    grades.setdefault(d, {}).setdefault(code.lower(), g)  # 먼저 채운(더 최근) 발표를 유지
            except Exception as e:
                bad += 1
                warnings.append(f"미세먼지 예보({code}) 조회 실패: {type(e).__name__}: {str(e)[:100]}")
        return bad

    with ThreadPoolExecutor(max_workers=3) as ex:
        f_rt = ex.submit(get_air_quality, sido) if need_realtime else None
        if need_forecast:
            failed += collect_forecast(ex, today)
            first, last = max(start, today), min(end, today + timedelta(days=2))
            needed = {(first + timedelta(days=i)).isoformat() for i in range((last - first).days + 1)}
            if failed == 0 and any(d not in grades for d in needed):
                failed += collect_forecast(ex, today - timedelta(days=1))  # 오늘 자 발표 전(새벽 등)이면 어제 발표분을 사용
            for d, g in grades.items():
                if lo <= d <= hi:
                    by_date[d] = {**g, "source": "예보"}
            if failed == 0 and not by_date:
                warnings.append("미세먼지 예보에 여행 기간 날짜가 없었습니다.")
        if f_rt is not None:
            try:
                realtime = summarize_realtime(f_rt.result())
            except Exception as e:
                warnings.append(f"미세먼지 실시간 조회 실패: {type(e).__name__}: {str(e)[:100]}")
            if realtime and today.isoformat() not in by_date:
                by_date[today.isoformat()] = {"pm10": realtime["pm10_grade"], "pm25": realtime["pm25_grade"], "source": "실측"}

    return {"by_date": by_date, "realtime": realtime, "warnings": warnings}
