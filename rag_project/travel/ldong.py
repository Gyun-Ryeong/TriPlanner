"""
시도 → 법정동 시도 코드(lDongRegnCd) 해석.

시도 코드는 행정구역 개편으로 바뀔 수 있어서(예: 광주·전남 통합 등), 코드를 하드코딩하지 않고
TourAPI의 ldongCode2 응답에서 이름으로 찾습니다. 조회에 실패하면 regions.py의 기본 코드를 씁니다.
결과는 파일로 캐시해서 API 호출을 아낍니다.
"""
import json
import threading
from pathlib import Path

from config import LDONG_CACHE_PATH
from travel.regions import SIDO

_lock = threading.Lock()
_mapping: dict[str, str] | None = None


def _load_mapping() -> dict[str, str]:
    """이름→코드 매핑. 캐시 파일 → API 순으로 시도하고, 실패하면 빈 dict."""
    global _mapping
    with _lock:
        if _mapping is not None:
            return _mapping
        path = Path(LDONG_CACHE_PATH)
        try:
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict) and data:
                    _mapping = data
                    return _mapping
        except Exception:
            pass
        try:
            from collectors.tourism import fetch_ldong_regions
            data = fetch_ldong_regions()
        except Exception:
            data = {}
        if data:
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            except Exception:
                pass
            _mapping = data
            return _mapping
        return {}  # 실패는 저장하지 않아 다음 요청에서 다시 시도


def _match(mapping: dict[str, str], sido: str) -> str | None:
    tokens = [sido] + SIDO[sido]["aliases"]
    for name, code in mapping.items():
        if any(t in name or name in t for t in tokens):
            return code
    return None


def resolve_ldong(sido: str) -> tuple[str, bool]:
    """
    Returns:
        (법정동 시도 코드, 여러 시도가 같은 코드를 공유하는지)
        공유하면(예: 광주·전남이 한 코드로 통합) 호출한 쪽에서 주소로 한 번 더 걸러야 합니다.
    """
    fallback = SIDO[sido]["ldong"]
    mapping = _load_mapping()
    if not mapping:
        return fallback, False
    code = _match(mapping, sido)
    if not code:
        return fallback, False
    shared = sum(1 for s in SIDO if _match(mapping, s) == code) > 1
    return code, shared


def reset_cache_for_tests() -> None:
    global _mapping
    _mapping = None


def resolve_sigungu(sido: str, area: str) -> list[tuple[str, str]]:
    """
    세부 지역명(예: '성남', '해운대', '분당구')에 해당하는 법정동 시군구 코드를 찾습니다.
    '성남'처럼 구가 여럿으로 나뉜 시는 해당하는 코드를 전부 돌려줍니다. 못 찾거나 조회에 실패하면 빈 리스트.
    (구가 아닌 명소 이름 — 예: '광안리' — 은 시군구가 아니므로 빈 리스트를 돌려주고, 호출한 쪽이 주소로 거릅니다)
    """
    area = (area or "").strip()
    if not area or sido not in SIDO:
        return []
    try:
        from collectors.tourism import fetch_ldong_sigungu
        code, _shared = resolve_ldong(sido)
        mapping = fetch_ldong_sigungu(code)
    except Exception:
        return []
    return [(name, c) for name, c in mapping.items() if area in name or name.replace(" ", "").startswith(area.replace(" ", ""))]
