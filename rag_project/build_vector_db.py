"""
장소 벡터 DB 채우기.

  python build_vector_db.py                 전국 (최근에 넣은 시군구는 건너뜀, 중간에 멈춰도 다시 실행하면 이어서)
  python build_vector_db.py 전북 강원        원하는 시도만
  python build_vector_db.py --force 부산     이미 있어도 다시 받기
  python build_vector_db.py --stats          저장된 장소 수 보기
  python build_vector_db.py --search "아이랑 갈 실내 박물관" 부산    DB에서 바로 검색해 보기
  python build_vector_db.py --reembed        API 없이 문장(분류 이름·받아 둔 소개글)만 다시 만들어 벡터 갱신
  python build_vector_db.py --overview 500 [부산]   소개글을 500곳 더 받고 그 장소 벡터 갱신 (관광지→문화시설→음식점 순)

TourAPI 호출 수: 시군구 하나에 보통 1~2번 (전국 약 250개 시군구 → 300번 안팎). 개발 계정 하루 한도 안에 들어간다.
임베딩 계산 때문에 전국은 수십 분 걸릴 수 있다.
"""
import sys
import time

import config
from concurrent.futures import ThreadPoolExecutor

from collectors.tourism import category_names, fetch_ldong_sigungu, get_overview, get_tourism_info, save_overviews
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


OVERVIEW_TYPES = ("12", "14", "39", "28", "38", "32")  # 관광지, 문화시설, 음식점, 레포츠, 쇼핑, 숙박


def _progress(done: int, total: int) -> None:
    print(f"  벡터 다시 계산 {done}/{total}", flush=True)


def reembed() -> None:
    _ensure_categories()
    t0 = time.time()
    n = PlaceDB().refresh_texts(progress=_progress)
    print(f"문장이 바뀐 {n}곳의 벡터를 다시 계산했어요 ({time.time() - t0:.0f}초)")


def fetch_overviews(limit: int, sido: str | None) -> None:
    """소개글을 limit곳 받아 캐시에 넣고, 그 장소들 벡터를 다시 계산한다. (개발 계정 하루 한도 안에서 나눠 실행)"""
    _ensure_categories()
    db = PlaceDB()
    regn = resolve_ldong(sido)[0] if sido else None
    todo = db.missing_overview_ids(OVERVIEW_TYPES, regn)[:limit]
    print(f"소개글을 받을 장소 {len(todo)}곳")
    found, fails = {}, 0

    def work(cid):
        try:
            return cid, get_overview(cid)
        except Exception:
            return cid, None

    with ThreadPoolExecutor(max_workers=6) as ex:
        for k, (cid, ov) in enumerate(ex.map(work, todo), 1):
            if ov is None:
                fails += 1
                if fails >= 20 and not found:
                    print("계속 실패해서 멈춰요. (하루 호출 한도를 넘었을 수 있어요)")
                    break
                continue
            found[cid] = ov or " "  # 소개글이 없는 장소도 다시 묻지 않게 표시
            if k % 100 == 0:
                print(f"  {k}/{len(todo)}")
                save_overviews(found)
    save_overviews(found)
    print(f"소개글 {len(found)}곳 받음 (실패 {fails})")
    n = db.refresh_texts(list(found), progress=_progress)
    print(f"벡터 {n}곳 갱신")


def _ensure_categories() -> None:
    try:
        n = len(category_names(fetch=True))
        print(f"분류 코드표 {n}개")
    except Exception as e:
        print(f"분류 코드표를 받지 못했어요 ({type(e).__name__}). 분류 이름 없이 진행해요")


def build(targets: list[str], force: bool) -> None:
    _ensure_categories()
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
    if not config.PUBLIC_DATA_API_KEY and not {"--stats", "--search", "--reembed"} & set(argv):
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
    if "--reembed" in argv:
        reembed()
        return
    if "--overview" in argv:
        i = argv.index("--overview")
        limit = int(argv[i + 1]) if len(argv) > i + 1 and argv[i + 1].isdigit() else 500
        rest = [a for a in argv[i + 2:] if not a.startswith("--")]
        fetch_overviews(limit, normalize_region(rest[0]) if rest else None)
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
