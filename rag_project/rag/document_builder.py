"""
각 API에서 수집한 dict 리스트를 벡터DB에 넣을 수 있는
(text, metadata) 형태의 '문서'로 변환합니다.
"""
import uuid


def build_documents(source: str, items: list[dict]) -> list[dict]:
    """
    Args:
        source: "tourism" | "weather" | "culture" | "air_quality" | "traffic" | "naver_news"
        items: 각 collectors 모듈이 반환한 list[dict]

    Returns:
        [{"id": ..., "text": ..., "metadata": {...}}, ...]
    """
    builders = {
        "tourism": _build_tourism,
        "weather": _build_weather,
        "culture": _build_culture,
        "air_quality": _build_air_quality,
        "traffic": _build_traffic,
        "naver_news": _build_naver_news,
    }
    builder = builders.get(source)
    if builder is None:
        raise ValueError(f"알 수 없는 source: {source}")

    docs = []
    for item in items:
        text = builder(item)
        docs.append({
            "id": str(uuid.uuid4()),
            "text": text,
            "metadata": {"source": source},
        })
    return docs


def _build_tourism(item: dict) -> str:
    return f"[관광정보] {item['title']} / 주소: {item.get('addr', '정보없음')}"


def _build_weather(item: dict) -> str:
    category_map = {"TMP": "기온", "POP": "강수확률", "SKY": "하늘상태", "PTY": "강수형태", "REH": "습도"}
    cat = category_map.get(item.get("category", ""), item.get("category", ""))
    return (
        f"[날씨예보-{item.get('region', '')}] {item.get('fcst_date', '')} "
        f"{item.get('fcst_time', '')} {cat}: {item.get('value', '')}"
    )


def _build_culture(item: dict) -> str:
    return f"[문화행사] {item['title']} / 기간: {item.get('period', '정보없음')} / 장소: {item.get('place', '정보없음')}"


def _build_air_quality(item: dict) -> str:
    return (
        f"[대기질-{item.get('sido', '')} {item.get('station', '')}] "
        f"측정시각: {item.get('data_time', '')}, PM10: {item.get('pm10', '정보없음')}, "
        f"PM2.5: {item.get('pm25', '정보없음')}, 통합대기환경지수 등급: {item.get('cai_grade', '정보없음')}"
    )


def _build_traffic(item: dict) -> str:
    return (
        f"[교통량] {item.get('road_name', '')} {item.get('spot_name', '')} "
        f"({item.get('std_year', '')}년) 교통량: {item.get('traffic_volume', '정보없음')}"
    )


def _build_naver_news(item: dict) -> str:
    return f"[뉴스-{item.get('pub_date', '')}] {item['title']}: {item.get('description', '')}"
