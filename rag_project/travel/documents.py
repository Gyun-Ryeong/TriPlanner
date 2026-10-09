"""장소 정보를 벡터DB에 넣을 문서로 변환."""
import uuid


def place_text(place: dict, sido: str) -> str:
    """유사도 순위용 문장. 소개글은 넣지 않아 같은 장소는 항상 같은 문장이 되고(임베딩 캐시 재사용), 가볍게 유지됩니다."""
    parts = [f"[{place.get('content_type', '')}-{sido}] {place.get('title', '')}"]
    if place.get("addr"):
        parts.append(f"주소: {place['addr']}")
    if place.get("event_start"):
        parts.append(f"행사기간: {place['event_start']}~{place.get('event_end', '')}")
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
