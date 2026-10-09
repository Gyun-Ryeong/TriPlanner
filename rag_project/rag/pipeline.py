"""
질문에 맞는 공공데이터 API들을 호출하고, 결과를 벡터 DB에 적재하는 파이프라인.

간단한 키워드 라우팅으로 "이 질문엔 어떤 API가 필요한지" 판단합니다.
(정교한 분류가 필요하면 이 부분을 Claude API 호출로 바꿔도 됩니다.)
"""
from datetime import datetime, timedelta

from collectors import (
    get_tourism_info,
    get_short_term_forecast,
    get_culture_info,
    get_air_quality,
    get_traffic_volume,
    search_news,
)
from rag.document_builder import build_documents
from rag.vector_store import VectorStore

ROUTING_KEYWORDS = {
    "tourism": ["관광", "여행", "명소", "가볼만한"],
    "weather": ["날씨", "기온", "비", "예보", "눈"],
    "culture": ["축제", "공연", "행사", "전시", "문화"],
    "air_quality": ["미세먼지", "대기질", "초미세먼지", "공기"],
    "traffic": ["교통량", "정체", "도로", "차량"],
}


def route_sources(question: str) -> list[str]:
    """질문 텍스트에 포함된 키워드로 어떤 소스를 조회할지 결정."""
    matched = [
        source for source, keywords in ROUTING_KEYWORDS.items()
        if any(kw in question for kw in keywords)
    ]
    # 아무 키워드도 안 걸리면 기본적으로 관광+문화 정도만 넓게 조회
    return matched or ["tourism", "culture"]


def fetch_and_index(question: str, region: str = "서울", store: VectorStore | None = None) -> VectorStore:
    """
    질문에 맞는 공공데이터 API + 네이버 뉴스를 호출해서 벡터 DB에 적재합니다.
    매 질문마다 새로 채워도 되고, store를 재사용해서 누적시켜도 됩니다.
    """
    store = store or VectorStore()
    sources = route_sources(question)
    all_docs = []

    if "tourism" in sources:
        items = get_tourism_info()
        all_docs += build_documents("tourism", items)

    if "weather" in sources:
        items = get_short_term_forecast(region=region)
        all_docs += build_documents("weather", items)

    if "culture" in sources:
        items = get_culture_info(keyword=question)
        all_docs += build_documents("culture", items)

    if "air_quality" in sources:
        items = get_air_quality(sido_name=region)
        all_docs += build_documents("air_quality", items)

    if "traffic" in sources:
        items = get_traffic_volume()
        all_docs += build_documents("traffic", items)

    # 뉴스는 항상 같이 조회해서 최신 트렌드 맥락을 보강
    try:
        news_items = search_news(question, display=5)
        all_docs += build_documents("naver_news", news_items)
    except ValueError:
        pass  # 네이버 키 미설정 시 조용히 스킵

    store.add_documents(all_docs)
    return store
