"""
기상청_단기예보 조회서비스
격자 좌표(nx, ny) 기준으로 단기예보를 조회하고 일자별로 요약합니다.
(단기예보는 발표 시점 기준 약 3일 이내만 제공됩니다)
"""
from datetime import datetime, timedelta

from config import ENDPOINTS
from collectors.base_client import call_public_api, extract_items
from collectors.cache import ttl_cache

# 시도별 대표 도시의 격자 좌표 (여행지 기준 대표 도시. 세부 지역과는 차이가 있을 수 있음)
REGION_GRID = {
    "서울": (60, 127),   # 서울
    "부산": (98, 76),    # 부산
    "대구": (89, 90),    # 대구
    "인천": (55, 124),   # 인천
    "광주": (58, 74),    # 광주
    "대전": (67, 100),   # 대전
    "울산": (102, 84),   # 울산
    "세종": (66, 103),   # 세종
    "경기": (60, 121),   # 수원
    "강원": (92, 131),   # 강릉
    "충북": (69, 107),   # 청주
    "충남": (63, 110),   # 천안
    "전북": (63, 89),    # 전주
    "전남": (73, 66),    # 여수
    "경북": (100, 91),   # 경주
    "경남": (90, 77),    # 창원
    "제주": (52, 38),    # 제주
}
GRID_COORDS = REGION_GRID  # 이전 이름 호환

BASE_HOURS = [2, 5, 8, 11, 14, 17, 20, 23]

PTY_NAMES = {0: "없음", 1: "비", 2: "비/눈", 3: "눈", 4: "소나기"}
SKY_NAMES = {1: "맑음", 3: "구름많음", 4: "흐림"}


def latest_base_datetime(now: datetime | None = None) -> tuple[str, str]:
    """
    지금 시점에서 조회 가능한 가장 최근 발표일/발표시각을 계산합니다.
    (발표 후 API에 반영되기까지 약 10분 걸려 15분 여유를 둡니다)
    """
    now = now or datetime.now()
    t = now - timedelta(minutes=15)
    hours = [h for h in BASE_HOURS if h <= t.hour]
    if hours:
        return t.strftime("%Y%m%d"), f"{max(hours):02d}00"
    prev = t - timedelta(days=1)
    return prev.strftime("%Y%m%d"), "2300"


@ttl_cache("weather", 1800, stale_ttl=6 * 3600, fail_cooldown=120)
def get_short_term_forecast(region: str = "서울", base_date: str = "", base_time: str = "") -> list[dict]:
    """
    단기예보 조회.

    Args:
        region: REGION_GRID에 정의된 시도명
        base_date: YYYYMMDD (비우면 현재 기준 자동 계산)
        base_time: 발표시각 HHMM (비우면 현재 기준 자동 계산)
    """
    nx, ny = REGION_GRID.get(region, REGION_GRID["서울"])
    if not base_date or not base_time:
        base_date, base_time = latest_base_datetime()

    params = {
        "numOfRows": 1000,  # 3일치 전 항목이 들어오도록 넉넉하게
        "pageNo": 1,
        "dataType": "JSON",
        "base_date": base_date,
        "base_time": base_time,
        "nx": nx,
        "ny": ny,
    }

    parsed = call_public_api(ENDPOINTS["weather"], params)
    items = extract_items(parsed)

    results = []
    for item in items:
        results.append({
            "source": "weather",
            "region": region,
            "category": item.get("category", ""),  # TMP=기온, TMN/TMX=최저/최고, POP=강수확률, SKY, PTY 등
            "fcst_date": item.get("fcstDate", ""),
            "fcst_time": item.get("fcstTime", ""),
            "value": item.get("fcstValue", ""),
            "raw": item,
        })
    return results


def summarize_daily(items: list[dict]) -> list[dict]:
    """
    get_short_term_forecast() 결과를 일자별 요약으로 바꿉니다.

    Returns:
        [{"date": "2026-09-29", "tmin": 18.0, "tmax": 25.0, "pop_max": 60,
          "precip": "비", "sky": "흐림", "wind_max": 4.2}, ...]
    """
    days: dict[str, dict] = {}
    for it in items:
        d = str(it.get("fcst_date", ""))
        if len(d) != 8:
            continue
        try:
            v = float(it.get("value", ""))
        except (TypeError, ValueError):
            continue
        day = days.setdefault(d, {"tmp": [], "tmn": None, "tmx": None, "pop": [], "pty": set(), "sky": [], "wsd": []})
        cat = it.get("category", "")
        if cat == "TMP":
            day["tmp"].append(v)
        elif cat == "TMN":
            day["tmn"] = v
        elif cat == "TMX":
            day["tmx"] = v
        elif cat == "POP":
            day["pop"].append(v)
        elif cat == "PTY":
            day["pty"].add(int(v))
        elif cat == "SKY":
            day["sky"].append(int(v))
        elif cat == "WSD":
            day["wsd"].append(v)

    out = []
    for d in sorted(days):
        x = days[d]
        tmin = x["tmn"] if x["tmn"] is not None else (min(x["tmp"]) if x["tmp"] else None)
        tmax = x["tmx"] if x["tmx"] is not None else (max(x["tmp"]) if x["tmp"] else None)
        precip = [PTY_NAMES.get(c, str(c)) for c in sorted(x["pty"]) if c != 0]
        sky = max(set(x["sky"]), key=x["sky"].count) if x["sky"] else None
        out.append({
            "date": f"{d[:4]}-{d[4:6]}-{d[6:]}",
            "tmin": tmin,
            "tmax": tmax,
            "pop_max": int(max(x["pop"])) if x["pop"] else None,
            "precip": "/".join(precip) if precip else "없음",
            "sky": SKY_NAMES.get(sky, "정보없음") if sky is not None else "정보없음",
            "wind_max": max(x["wsd"]) if x["wsd"] else None,
        })
    return out
