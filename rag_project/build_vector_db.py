"""
장소 벡터 DB 채우기.

  python build_vector_db.py                 전국 (최근에 넣은 시군구는 건너뜀, 중간에 멈춰도 다시 실행하면 이어서)
  python build_vector_db.py 전북 강원        원하는 시도만
  python build_vector_db.py --force 부산     이미 있어도 다시 받기
  python build_vector_db.py --stats          저장된 장소 수 보기
  python build_vector_db.py --search "아이랑 갈 실내 박물관" 부산    DB에서 바로 검색해 보기

TourAPI 호출 수: 시군구 하나에 보통 1~2번 (전국 약 250개 시군구 → 300번 안팎). 개발 계정 하루 한도 안에 들어간다.
임베딩 계산 때문에 전국은 수십 분 걸릴 수 있다.
"""
import sys
import time

import config
from collectors.tourism import fetch_ldong_sigungu, get_tourism_info
from travel.gazetteer import _owners
from travel.ldong import resolve_ldong
from travel.pipeline import WANTED_TYPES
from travel.place_db import SKIP_TYPES, PlaceDB
from travel.regions import SIDO, normalize_region

ROWS = 1000
RETRY_ROWS = 200  # 한 번에 1000곳을 받다가 시간 초과가 나면 이만큼씩 나눠서 다시 받는다
MAX_FAILS = 5  # 연속으로 이만큼 실패하면 (호출 한도 초과 등) 멈춘다
_fetch = getattr(get_tourism_info, "__wrapped__", get_tourism_info)  # 파일 캐시(cache/api)를 거치지 않는다


def fetch_all(code: str, scode: str, rows: int = ROWS) -> tuple[list[dict], int]:
    """한 시군구의 장소를 페이지를 넘겨 가며 전부 받는다. (장소 목록, 호출 수)"""
    out, page, calls = [], 1, 0
    while True:
        got = _fetch(l_dong_regn_cd=code, l_dong_signgu_cd=scode, num_rows=rows, page=page)
        calls += 1
        out += [p for p in got if p["content_type_id"] in WANTED_TYPES and p["content_type_id"] not in SKIP_TYPES]
        if len(got) < rows or page >= 100:
            return out, calls
        page += 1


def fetch_with_retry(code: str, scode: str, name: str) -> tuple[list[dict], int]:
    try:
        return fetch_all(code, scode)
    except Exception as e:
        print(f"  … {name}: 한 번에 받기 실패({type(e).__name__}), {RETRY_ROWS}곳씩 나눠서 다시 받아요")
        places, calls = fetch_all(code, scode, RETRY_ROWS)
        return places, calls + 1


def sigungu_of(sido: str) -> tuple[str, dict[str, str]]:
    """(시도 코드, {시군구 이름: 코드}) — 광주·전남처럼 코드를 함께 쓰면 그 시도 몫만"""
    code, shared = resolve_ldong(sido)
    names = fetch_ldong_sigungu(code)
    if shared:
        sharing = [s for s in SIDO if resolve_ldong(s)[0] == code]
        names = {n: c for n, c in names.items() if sido in _owners(n, sharing)}
    return code, names


def build(targets: list[str], force: bool) -> None:
    db = PlaceDB()
    total_places = total_calls = fails = 0
    t0 = time.time()
    for sido in targets:
        try:
            code, names = sigungu_of(sido)
        except Exception as e:
            print(f"[{sido}] 시군구 목록을 받지 못했어요: {type(e).__name__}")
            fails += 1
            if fails >= MAX_FAILS:
                break
            continue
        print(f"[{sido}] 시군구 {len(names)}곳")
        for name, scode in names.items():
            if not force and db.is_fresh(code, scode):
                print(f"  - {name}: 이미 있음 (건너뜀)")
                continue
            try:
                places, calls = fetch_with_retry(code, scode, name)
                total_calls += calls
            except Exception as e:
                fails += 1
                print(f"  ! {name}: 받기 실패 {type(e).__name__}: {str(e)[:80]}")
                if fails >= MAX_FAILS:
                    print(f"연속 {MAX_FAILS}번 실패해서 멈춰요. (하루 호출 한도를 넘었을 수 있어요. 내일 다시 실행하면 이어서 채워요)")
                    return _summary(db, total_places, total_calls, t0)
                continue
            fails = 0
            if not places:
                print(f"  - {name}: 0곳 (저장 안 함)")
                continue
            n = db.put_region(code, scode, places, lambda p, s=sido: s)
            total_places += n
            print(f"  + {name}: {n}곳 저장")
    _summary(db, total_places, total_calls, t0)


def _summary(db: PlaceDB, places: int, calls: int, t0: float) -> None:
    s = db.stats()
    print(f"\n이번에 저장 {places}곳, TourAPI {calls}번 호출, {time.time() - t0:.0f}초")
    print(f"DB 전체: 장소 {s['places']}곳, 시군구 {s['regions']}곳 ({s['path']})")


def main(argv: list[str]) -> None:
    if not config.PUBLIC_DATA_API_KEY and "--stats" not in argv and "--search" not in argv:
        print(".env 에 PUBLIC_DATA_API_KEY 가 없어요.")
        return
    if "--stats" in argv:
        s = PlaceDB().stats()
        print(f"장소 {s['places']}곳, 시군구 {s['regions']}곳 ({s['path']})")
        return
    if "--search" in argv:
        i = argv.index("--search")
        query = argv[i + 1] if len(argv) > i + 1 else ""
        sido = normalize_region(argv[i + 2]) if len(argv) > i + 2 else None
        regn = resolve_ldong(sido)[0] if sido else None
        for p in PlaceDB().search(query, regn, k=10):
            print(f"{p['distance']:.3f}  [{p.get('content_type', '')}] {p['title']}  ({p.get('addr', '')})")
        return
    force = "--force" in argv
    names = [a for a in argv if not a.startswith("--")]
    targets = [normalize_region(a) for a in names] if names else list(SIDO)
    bad = [a for a, t in zip(names, targets) if t not in SIDO]
    if bad:
        print(f"모르는 시도: {', '.join(bad)}. 가능: {', '.join(SIDO)}")
        return
    build(list(dict.fromkeys(targets)), force)


if __name__ == "__main__":
    main(sys.argv[1:])
