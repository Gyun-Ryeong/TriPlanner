"""
API 응답 캐시 (메모리 + 파일).

같은 요청을 짧은 시간에 반복해도 외부 API를 다시 부르지 않습니다. 파일로도 저장하기 때문에
프로그램을 다시 실행해도 유지됩니다. (성공한 '비어 있지 않은' 결과만 저장하고, 오류는 저장하지 않습니다)
끄려면 .env에 API_CACHE=off
"""
import copy
import functools
import hashlib
import json
import os
import threading
import time
from pathlib import Path

import config

_mem: dict[str, tuple[float, object]] = {}
_fail: dict[str, float] = {}  # 최근 실패 시각 (연속 호출로 느린 서버를 또 기다리지 않기 위함)
_lock = threading.Lock()
STALE_EVENTS: list[str] = []  # 오래된 저장본을 대신 쓴 기록 (개발 모드 정보용)


def pop_stale_events() -> list[str]:
    with _lock:
        out = list(dict.fromkeys(STALE_EVENTS))
        STALE_EVENTS.clear()
    return out


def ttl_cache(name: str, ttl_sec: int, stale_ttl: int = 0, fail_cooldown: int = 0):
    """
    함수 결과를 ttl_sec초 동안 재사용. 결과는 JSON으로 저장 가능해야 합니다.
    stale_ttl: 호출이 실패하면 이 시간(초) 안의 오래된 저장본으로 대신 답한다.
    fail_cooldown: 실패 후 이 시간(초) 동안은 같은 요청을 다시 시도하지 않고 바로 실패/저장본을 쓴다.
    """

    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            if not config.API_CACHE_ENABLED or ttl_sec <= 0:
                return fn(*args, **kwargs)
            raw_key = json.dumps([name, args, sorted(kwargs.items())], ensure_ascii=False, default=str)
            key = hashlib.sha1(raw_key.encode("utf-8")).hexdigest()
            now = time.time()
            path = Path(config.API_CACHE_DIR) / f"{name}_{key}.json"
            with _lock:
                hit = _mem.get(key)
            if hit and now - hit[0] < ttl_sec:
                return copy.deepcopy(hit[1])  # 호출한 쪽이 고쳐 써도 캐시가 변하지 않게 복사본을 준다
            disk = None
            try:
                if path.exists():
                    disk = json.loads(path.read_text(encoding="utf-8"))
                    if now - disk["t"] < ttl_sec:
                        with _lock:
                            _mem[key] = (disk["t"], disk["v"])
                        return copy.deepcopy(disk["v"])
            except Exception:
                disk = None

            def stale():
                cand = hit if hit else ((disk["t"], disk["v"]) if disk else None)
                if cand and stale_ttl and now - cand[0] < stale_ttl and cand[1]:
                    with _lock:
                        STALE_EVENTS.append(f"{name}: 서버가 응답하지 않아 {int((now - cand[0]) / 60)}분 전 저장본을 사용했어요.")
                    return copy.deepcopy(cand[1])
                return None

            with _lock:
                failed_at = _fail.get(key, 0)
            if fail_cooldown and now - failed_at < fail_cooldown:
                old = stale()
                if old is not None:
                    return old
                raise RuntimeError(f"{name}: 직전 요청이 실패해 {fail_cooldown // 60}분간 재시도를 쉬고 있어요.")
            try:
                result = fn(*args, **kwargs)
            except Exception:
                with _lock:
                    _fail[key] = time.time()
                old = stale()
                if old is not None:
                    return old
                raise
            with _lock:
                _fail.pop(key, None)
            if result:  # 빈 결과는 일시적일 수 있어 저장하지 않는다
                with _lock:
                    _mem[key] = (now, result)
                try:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    tmp = path.with_suffix(f".{os.getpid()}.{threading.get_ident()}.tmp")
                    tmp.write_text(json.dumps({"t": now, "v": result}, ensure_ascii=False), encoding="utf-8")
                    os.replace(tmp, path)
                except Exception:
                    pass
            return copy.deepcopy(result)

        return wrapper

    return deco


def clear_memory() -> None:
    with _lock:
        _mem.clear()
        _fail.clear()
        STALE_EVENTS.clear()
