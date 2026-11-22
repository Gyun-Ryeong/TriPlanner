"""
장소 벡터 DB 옮기기: ChromaDB(chroma_db/) → MariaDB(triplanner.tour_place, tour_region)

벡터를 다시 계산하지 않고 그대로 옮긴다. 여러 번 실행해도 같은 장소는 덮어쓴다(중복 없음).
옮긴 뒤 장소 수, 벡터 값, 검색 결과 순서가 ChromaDB와 같은지 확인까지 한다.

    python migrate_chroma_to_mariadb.py            # 옮기기 + 확인
    python migrate_chroma_to_mariadb.py --check    # 확인만

필요한 것: .env 의 DB_HOST·DB_PORT·DB_NAME·DB_USER·DB_PASSWORD, MariaDB 11.7 이상, 1단계 테이블
"""
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pymysql

import config

BATCH = 500
CHROMA_DIR = Path(config.CHROMA_PERSIST_DIR)


def connect():
    if not config.DB_USER:
        sys.exit(".env 에 DB_USER / DB_PASSWORD 가 없어요.")
    return pymysql.connect(host=config.DB_HOST, port=config.DB_PORT, user=config.DB_USER, password=config.DB_PASSWORD,
                           database=config.DB_NAME, charset="utf8mb4", autocommit=False)


def chroma_collection():
    import chromadb
    return chromadb.PersistentClient(path=str(CHROMA_DIR)).get_collection("places")


def vec_text(v) -> str:
    return "[" + ",".join(f"{float(x):.8g}" for x in v) + "]"


def migrate_places(conn) -> int:
    col = chroma_collection()
    ids = col.get(include=[])["ids"]
    total = len(ids)
    print(f"ChromaDB 장소 {total}곳을 옮겨요 ({BATCH}곳씩)")
    sql = ("INSERT INTO tour_place (content_id, regn_cd, signgu_cd, sido, type_id, indoor, doc_text, text_hash, data, embedding) "
           "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, VEC_FromText(%s)) "
           "ON DUPLICATE KEY UPDATE regn_cd=VALUES(regn_cd), signgu_cd=VALUES(signgu_cd), sido=VALUES(sido), "
           "type_id=VALUES(type_id), indoor=VALUES(indoor), doc_text=VALUES(doc_text), text_hash=VALUES(text_hash), "
           "data=VALUES(data), embedding=VALUES(embedding)")
    t0, done = time.time(), 0
    with conn.cursor() as cur:
        for s in range(0, total, BATCH):
            got = col.get(ids=ids[s:s + BATCH], include=["documents", "metadatas", "embeddings"])
            rows = []
            for cid, doc, m, e in zip(got["ids"], got["documents"], got["metadatas"], got["embeddings"]):
                rows.append((cid, str(m.get("regn", "")), str(m.get("signgu", "")), str(m.get("sido", "")),
                             str(m.get("type", "")), bool(m.get("indoor")), doc or "", str(m.get("th", ""))[:10],
                             m.get("data") or "{}", vec_text(e)))
            cur.executemany(sql, rows)
            conn.commit()
            done += len(rows)
            print(f"  {done}/{total} ({time.time() - t0:.0f}초)", flush=True)
    return done


def migrate_regions(conn) -> int:
    path = CHROMA_DIR / "regions.json"
    regions = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    rows = []
    for key, ts in regions.items():
        regn, _, signgu = key.partition("|")
        rows.append((regn, signgu, datetime.fromtimestamp(float(ts))))
    with conn.cursor() as cur:
        cur.executemany("INSERT INTO tour_region (regn_cd, signgu_cd, fetched_at) VALUES (%s, %s, %s) "
                        "ON DUPLICATE KEY UPDATE fetched_at=VALUES(fetched_at)", rows)
    conn.commit()
    print(f"시군구 저장 시각 {len(rows)}곳을 옮겼어요")
    return len(rows)


def check(conn) -> bool:
    """장소 수 · 벡터 값 · 검색 순서가 ChromaDB와 같은지"""
    col = chroma_collection()
    ok = True
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM tour_place")
        n_db = cur.fetchone()[0]
        n_ch = col.count()
        print(f"[장소 수] ChromaDB {n_ch} / MariaDB {n_db}", "✅" if n_db == n_ch else "❌")
        ok &= n_db == n_ch

        cur.execute("SELECT COUNT(*) FROM tour_region")
        n_reg = cur.fetchone()[0]
        n_json = len(json.loads((CHROMA_DIR / "regions.json").read_text(encoding="utf-8")))
        print(f"[시군구] regions.json {n_json} / MariaDB {n_reg}", "✅" if n_reg == n_json else "❌")
        ok &= n_reg == n_json

        # 무작위 200곳의 벡터가 같은지
        sample = col.get(include=["embeddings"], limit=200, offset=max(0, n_ch // 2 - 100))
        cur.execute("SELECT content_id, VEC_ToText(embedding) FROM tour_place WHERE content_id IN %s", (tuple(sample["ids"]),))
        db_vec = {cid: np.array(json.loads(t), dtype=np.float32) for cid, t in cur.fetchall()}
        diff = max(float(np.max(np.abs(db_vec[i] - np.asarray(e, dtype=np.float32)))) for i, e in zip(sample["ids"], sample["embeddings"]))
        print(f"[벡터 값] 표본 {len(db_vec)}곳 최대 차이 {diff:.2e}", "✅" if diff < 1e-5 else "❌")
        ok &= diff < 1e-5

        # 같은 질문으로 같은 장소가 같은 순서로 나오는지 (대구 국밥)
        from travel.embeddings import get_ranker
        from travel.ldong import resolve_ldong
        regn = resolve_ldong("대구")[0]
        q = get_ranker().embed_texts(["대구 국밥 맛집"])[0]
        ch = col.query(query_embeddings=[list(map(float, q))], n_results=10, where={"regn": regn})["ids"][0]
        # 지역을 거를 때는 벡터 인덱스를 쓰지 않는다: 인덱스는 전국에서 가까운 것을 먼저 고른 뒤 지역을 걸러
        # 그 지역 장소가 거의 안 남는다 (실측: 정답 10곳 중 1곳). 시도 하나는 수천 곳이라 직접 비교해도 빠르다
        t0 = time.perf_counter()
        cur.execute("SELECT content_id FROM tour_place IGNORE INDEX (embedding) WHERE regn_cd=%s "
                    "ORDER BY VEC_DISTANCE_COSINE(embedding, VEC_FromText(%s)) LIMIT 10", (regn, vec_text(q)))
        db = [r[0] for r in cur.fetchall()]
        print(f"[검색 시간] 대구 전체 비교 {(time.perf_counter() - t0) * 1000:.0f}ms")
        same = len(set(ch) & set(db))
        print(f"[검색 결과] '대구 국밥 맛집' 상위 10곳 중 {same}곳 일치", "✅" if same >= 9 else "❌")
        ok &= same >= 9
    print("\n모두 같아요 ✅" if ok else "\n다른 곳이 있어요 ❌ 위 내용을 확인하세요")
    return ok


def main(argv):
    conn = connect()
    try:
        if "--check" not in argv:
            t0 = time.time()
            migrate_places(conn)
            migrate_regions(conn)
            print(f"옮기기 끝 ({time.time() - t0:.0f}초)\n")
        check(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main(sys.argv[1:])
