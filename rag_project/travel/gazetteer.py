"""
전국 기초지자체(시·군·구) 이름 사전.

regions.py의 도시 목록에 없는 지역(예: 곡성, 영월, 울진)도 인식하기 위해 TourAPI의 법정동 시군구 목록(ldongCode2)으로
이름 → 시도 사전을 만들어 파일에 저장해 둡니다. (최초 1회 시도 코드 수만큼 호출, 이후 30일간 재사용)

- 여러 시도가 한 코드를 함께 쓰면(예: 광주·전남이 '전남광주통합특별시' 하나로 통합) '구'는 광역시, 나머지(시·군)는 도로 나눕니다.
- '고성'(강원·경남), '중구'(여러 광역시)처럼 여러 시도에 같은 이름이 있으면 이름만으로는 고르지 않고,
  시도를 함께 말했을 때(lookup_in_sido) 쓰거나 어느 쪽인지 되묻습니다(ambiguous_regions).

오인 방지: '고양이', '화성(행성)' 같은 일상 단어가 지명으로 읽히지 않도록, 일반 방식으로 지역을 못 찾았을 때만 쓰고
일상 단어와 같은 이름은 '고양시'처럼 시·군·구를 붙이거나 여행 이야기('광명 1박2일', '이천 여행')일 때만 인식합니다.
"""
import json
import re
import threading
import time
from pathlib import Path

import config
from travel.news import variants

_lock = threading.Lock()
_index: dict[str, list[str]] | None = None  # 이름('곡성', '중구') → 그 이름이 있는 시도들(['전남'])
# 지명과 같은 글자인 일상 단어 (고양이, 화성(행성), 이천(2000), 인제(이제), 상주(머무름), 장수(오래 삶), 진도(진행), 보은(은혜 갚음) 등)
COMMON_WORDS = {"고양", "구리", "화성", "이천", "인제", "상주", "장수", "진도", "보은", "영동", "안성", "광명", "오산", "부여", "서산", "남해", "금산"}
# 일상 단어와 같은 지명도 이런 말과 함께 나오면 지명으로 본다 ("광명 1박2일", "이천 여행 가자")
TRIP_CONTEXT_RE = re.compile(r"여행|일정|\d+\s*박|당일|코스|놀러|가고|갈래|가자|갈까|가려|간다|가요|추천|맛집|축제|관광|명소|숙소")
_PLAIN_PARTICLE = r"(?:에서|으로|부터|까지|에|로|쪽|은|는|도)?"
METRO = {"서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종"}
# 행정구역 개편으로 사라진 옛 이름 → 지금 이름 (TourAPI 목록에는 새 이름만 있다). 사람들은 옛 이름으로 말하는 경우가 많다
LEGACY_NAMES = {("인천", "중구"): "제물포", ("인천", "동구"): "제물포", ("인천", "서구"): "서해"}
TTL = 30 * 24 * 3600
FAIL_COOLDOWN = 300
_failed_at = 0.0


def _keys(full: str) -> list[str]:
    """'성남시 분당구' → ['성남', '분당'], '곡성군' → ['곡성'], '중구' → ['중구'] (한 글자 이름은 '구'까지 붙여서)"""
    out = []
    for w in full.split():
        c = re.sub(r"(특별자치시|특별시|광역시|시|군|구)$", "", w)
        if len(c) >= 2:
            out.append(c)
        elif len(w) >= 2:
            out.append(w)
    return out


def _owners(full: str, sidos: list[str]) -> list[str]:
    """한 코드를 여러 시도가 함께 쓸 때 이 시군구의 시도. '구'는 광역시 쪽, 시·군은 도 쪽."""
    if len(sidos) == 1:
        return sidos
    metro = [s for s in sidos if s in METRO]
    province = [s for s in sidos if s not in METRO]
    is_gu = full.split()[0].endswith("구")
    return (metro if is_gu else province) or sidos


def _build() -> dict[str, list[str]]:
    from collectors.tourism import fetch_ldong_sigungu
    from travel.ldong import resolve_ldong
    from travel.regions import SIDO

    by_code: dict[str, list[str]] = {}
    for sido in SIDO:
        try:
            code, _ = resolve_ldong(sido)
        except Exception:
            continue
        by_code.setdefault(code, []).append(sido)

    idx: dict[str, list[str]] = {}
    for code, sidos in by_code.items():
        try:
            names = fetch_ldong_sigungu(code)
        except Exception:
            continue
        for full in names:
            for owner in _owners(full, sidos):
                for key in _keys(full):
                    if owner not in idx.setdefault(key, []):
                        idx[key].append(owner)
    return idx


def _load() -> dict[str, list[str]]:
    global _index
    with _lock:
        if _index is not None:
            return _index
        path = Path(config.GAZETTEER_CACHE_PATH)
        try:
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                if time.time() - data["t"] < TTL and data.get("v2"):  # 예전 형식("v")은 모호한 이름을 잃어서 다시 만든다
                    _index = data["v2"]
                    return _index
        except Exception:
            pass
        global _failed_at
        if time.time() - _failed_at < FAIL_COOLDOWN:
            return {}  # 방금 실패했으면 잠시 동안 다시 시도하지 않는다 (API를 계속 두드리지 않기 위해)
        built = _build()
        if not built:
            _failed_at = time.time()
        if built:  # 실패(빈 결과)는 저장하지 않아 다음에 다시 시도
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps({"t": time.time(), "v2": built}, ensure_ascii=False), encoding="utf-8")
            except Exception:
                pass
            _index = built
            return _index
        return {}


def _matches(text: str) -> list[tuple[str, list[str]]]:
    """문장 속 시군구 이름을 등장 순서대로 (이름, 시도들)."""
    idx = _load()
    if not idx:
        return []
    trip_talk = bool(TRIP_CONTEXT_RE.search(text or ""))
    found: list[tuple[str, list[str]]] = []
    for raw in re.sub(r"[?!.,~]", " ", text or "").split():
        for cand in dict.fromkeys(variants(raw)):
            has_suffix = len(cand) > 2 and cand.endswith(("시", "군", "구"))
            core = cand[:-1] if has_suffix else cand
            if core in COMMON_WORDS and not has_suffix:
                # '고양이랑'의 '고양'처럼 일상 단어와 겹치는 이름은 '고양시'처럼 시·군·구를 붙이거나,
                # 단어 그대로("광명", "광명에서") 여행 이야기 속에 나올 때만 지명으로 본다
                if not (trip_talk and re.fullmatch(re.escape(core) + _PLAIN_PARTICLE, raw)):
                    continue
            sidos = idx.get(core) or idx.get(cand)
            if sidos:
                name = core if core in idx else cand
                if name not in [n for n, _ in found]:
                    found.append((name, sidos))
                break
    return found


def lookup_regions(text: str) -> list[tuple[str, str]]:
    """문장 속 기초지자체 이름을 등장 순서대로 (시도, 이름)으로. 여러 시도에 있는 이름(모호)은 뺀다."""
    return [(sidos[0], name) for name, sidos in _matches(text) if len(sidos) == 1]


def lookup_in_sido(text: str, sido: str) -> str:
    """시도를 함께 말했을 때 그 시도 안의 시군구 이름 ('강원 고성' → '고성', '부산 중구' → '중구'). 없으면 ''."""
    names = [name for name, sidos in _matches(text) if sido in sidos]
    if not names:
        names = [new for (s, old), new in LEGACY_NAMES.items() if s == sido and old in (text or "")]
    return names[-1] if names else ""


def ambiguous_regions(text: str) -> list[tuple[str, list[str]]]:
    """여러 시도에 있어서 어느 쪽인지 모르는 이름. 예) '고성 1박2일' → [('고성', ['강원', '경남'])]"""
    return [(name, sidos) for name, sidos in _matches(text) if len(sidos) > 1]


def reset_for_tests() -> None:
    global _index, _failed_at
    _index, _failed_at = None, 0.0
