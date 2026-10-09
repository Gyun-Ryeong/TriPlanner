"""
전국 기초지자체(시·군·구) 이름 사전.

regions.py의 도시 목록에 없는 지역(예: 곡성, 영월, 울진)도 인식하기 위해 TourAPI의 법정동 시군구 목록(ldongCode2)으로
이름 → 시도 사전을 만들어 파일에 저장해 둡니다. (최초 1회 시도 수만큼 호출, 이후 30일간 재사용)

오인 방지: '고양이', '화성(행성)' 같은 일상 단어가 지명으로 읽히지 않도록, 일반 방식으로 지역을 못 찾았을 때만 쓰고
'고성'처럼 여러 시도에 같은 이름이 있으면 모호하므로 건너뜁니다(시도를 함께 말하면 일반 방식이 처리).
"""
import json
import re
import threading
import time
from pathlib import Path

import config
from travel.news import variants

_lock = threading.Lock()
_index: dict[str, str] | None = None  # 핵심 이름('곡성') → 시도('전남') / 모호하면 ''
# 지명과 같은 글자인 일상 단어 (고양이, 화성(행성), 이천(2000), 인제(이제), 상주(머무름), 장수(오래 삶), 진도(진행), 보은(은혜 갚음) 등)
COMMON_WORDS = {"고양", "구리", "화성", "이천", "인제", "상주", "장수", "진도", "보은", "영동", "안성", "광명", "오산", "부여", "서산", "남해", "금산"}
TTL = 30 * 24 * 3600
FAIL_COOLDOWN = 300
_failed_at = 0.0


def _core_names(full: str) -> list[str]:
    """'성남시 분당구' → ['성남', '분당'], '곡성군' → ['곡성']"""
    out = []
    for w in full.split():
        c = re.sub(r"(특별자치시|특별시|광역시|시|군|구)$", "", w)
        if len(c) >= 2:
            out.append(c)
    return out


def _build() -> dict[str, str]:
    from collectors.tourism import fetch_ldong_sigungu
    from travel.ldong import resolve_ldong
    from travel.regions import SIDO

    idx: dict[str, str] = {}
    for sido in SIDO:
        try:
            code, _ = resolve_ldong(sido)
            names = fetch_ldong_sigungu(code)
        except Exception:
            continue
        for full in names:
            for core in _core_names(full):
                idx[core] = "" if idx.get(core, sido) != sido else sido  # 다른 시도에도 있으면 모호
    return idx


def _load() -> dict[str, str]:
    global _index
    with _lock:
        if _index is not None:
            return _index
        path = Path(config.GAZETTEER_CACHE_PATH)
        try:
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                if time.time() - data["t"] < TTL and data["v"]:
                    _index = data["v"]
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
                path.write_text(json.dumps({"t": time.time(), "v": built}, ensure_ascii=False), encoding="utf-8")
            except Exception:
                pass
            _index = built
            return _index
        return {}


def lookup_regions(text: str) -> list[tuple[str, str]]:
    """문장 속 기초지자체 이름을 등장 순서대로 (시도, 이름)으로. 모호하거나 없으면 빈 리스트."""
    idx = _load()
    if not idx:
        return []
    found: list[tuple[str, str]] = []
    for raw in re.sub(r"[?!.,~]", " ", text or "").split():
        for cand in dict.fromkeys(variants(raw)):
            has_suffix = len(cand) > 2 and cand.endswith(("시", "군", "구"))
            core = cand[:-1] if has_suffix else cand
            if core in COMMON_WORDS and not has_suffix:
                continue  # '고양이랑'의 '고양'처럼 일상 단어와 겹치는 이름은 '고양시'처럼 시·군·구를 붙여야 인식
            sido = idx.get(core) or idx.get(cand)
            if sido and (sido, core) not in found:
                found.append((sido, core))
                break
    return found


def reset_for_tests() -> None:
    global _index, _failed_at
    _index, _failed_at = None, 0.0
