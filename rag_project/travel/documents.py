"""장소 정보를 벡터DB에 넣을 문서로 변환."""
import uuid


OVERVIEW_CHARS = 120  # 임베딩 모델이 앞쪽 128토큰만 보므로 소개글은 앞부분만


def place_text(place: dict, sido: str) -> str:
    """
    유사도 순위용 문장: '[관광지-부산] 해운대해수욕장 | 분류: 해변 | 소개: … | 주소: …'
    - 분류 이름(카페·해수욕장·자연휴양림…)과 소개글이 있어야 '바다 보이는 카페' 같은 말과 비교가 된다.
    - 소개글은 받아 둔 것(캐시)만 쓴다. 그래서 같은 장소는 언제 만들어도 같은 문장 → 벡터 DB·캐시를 재사용.
    - 모델이 앞부분만 보므로 의미가 큰 것부터: 이름 → 분류 → 소개 → 주소.
    """
    from collectors.tourism import cached_overview, category_label

    parts = [f"[{place.get('content_type', '')}-{sido}] {place.get('title', '')}"]
    if cat := category_label(place.get("raw")):
        parts.append(f"분류: {cat}")
    overview = place.get("overview") or cached_overview(place.get("content_id"))
    if overview:
        parts.append("소개: " + overview[:OVERVIEW_CHARS])
    if place.get("event_start"):
        parts.append(f"행사기간: {place['event_start']}~{place.get('event_end', '')}")
    if place.get("addr"):
        parts.append(f"주소: {place['addr']}")
    return " | ".join(parts)


def place_to_document(place: dict, sido: str, request_id: str) -> dict:
    parts = [f"[{place.get('content_type', '')}-{sido}] {place.get('title', '')}"]
    if place.get("addr"):
        parts.append(f"주소: {place['addr']}")
    if place.get("overview"):
        parts.append("소개: " + place["overview"][:300])
    if place.get("event_start"):
        parts.append(f"행사기간: {place['event_start']}~{place.get('event_end', '')}")

    cid = place.get("content_id") or uuid.uuid4().hex
    return {
        "id": f"{request_id}:{cid}",
        "text": " | ".join(parts),
        # 상세 정보는 서버 메모리의 place dict로 다시 찾기 때문에 metadata는 최소한만 저장
        "metadata": {"source": "tourism", "request_id": request_id, "content_id": str(cid)},
    }
