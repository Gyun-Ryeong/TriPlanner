"""
장소 벡터 DB (MariaDB, 백엔드와 같은 triplanner DB).

전국 관광지·음식점 등을 미리 저장해 두고, 일정을 짤 때 TourAPI를 부르지 않고 여기서 꺼내 씁니다.
- 채우는 방법 1: build_vector_db.py 로 미리 전국(또는 원하는 시도)을 넣는다.
- 채우는 방법 2: DB에 없는 지역을 누가 물어보면 TourAPI로 받은 결과를 그대로 저장한다 (쓰면서 채워짐).
- 예전 ChromaDB(chroma_db/)에서 옮기기: migrate_chroma_to_mariadb.py

저장 단위는 TourAPI 호출 단위와 같은 '법정동 시도 코드 + 시군구 코드'입니다.
지역마다 언제 저장했는지 기록해 두고(tour_region), PLACE_DB_MAX_AGE_DAYS가 지나면 다시 받아 새로 고칩니다.
축제(15)는 날짜가 자주 바뀌어 저장하지 않고 계속 실시간으로 받습니다.

테이블 (로컬: MariaDB 11.7 이상 VECTOR(384) / 배포: AWS RDS MySQL varbinary(1536) — 코드는 둘 다 바이트로 읽어서 같다)
  tour_place  : content_id(PK), regn_cd, signgu_cd, sido, type_id, indoor, doc_text(검색용 문장),
                text_hash, data(장소 정보 JSON), embedding VECTOR(384)
  tour_region : regn_cd, signgu_cd (PK), fetched_at

벡터는 float32 바이트로 넣고 읽는다. 유사도 검색은 그 지역 장소만 꺼내 numpy로 정확히 계산한다.
(MariaDB 벡터 인덱스는 전국에서 가까운 것을 먼저 고른 뒤 지역을 걸러, 지역 검색에서는 정답이 거의 빠졌다. 실측 10곳 중 1곳)
"""
import hashlib
import json
import threading
import time
from datetime import datetime

import numpy as np

import config

SKIP_TYPES = {"15"}  # 축제·행사는 저장하지 않는다
_RAW_KEYS = ("lclsSystm1", "lclsSystm2", "lclsSystm3", "tel")  # 원본 응답 중 다른 기능이 쓰는 값만 남긴다
_CHUNK = 1000  # IN (…) 한 번에 넣을 id 수

# 테스트용 SQLite 스키마 (MariaDB 테이블과 같은 모양, 벡터는 BLOB)
SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS tour_place (
  content_id TEXT PRIMARY KEY, regn_cd TEXT NOT NULL, signgu_cd TEXT NOT NULL, sido TEXT NOT NULL,
  type_id TEXT NOT NULL, indoor INTEGER NOT NULL, doc_text TEXT NOT NULL, text_hash TEXT NOT NULL,
  data TEXT NOT NULL, embedding BLOB NOT NULL);
CREATE TABLE IF NOT EXISTS tour_region (regn_cd TEXT, signgu_cd TEXT, fetched_at TEXT, PRIMARY KEY (regn_cd, signgu_cd));
"""


def text_hash(text: str) -> str:
    """PlaceRanker의 캐시 키와 같은 방식 (같은 문장이면 같은 벡터를 재사용)"""
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]


def _slim(place: dict) -> dict:
    p = {k: v for k, v in place.items() if k not in ("raw", "nearby", "issue", "issues")}
    p["raw"] = {k: (place.get("raw") or {}).get(k, "") for k in _RAW_KEYS}
    return p


def _to_bytes(vec) -> bytes:
    return np.asarray(vec, dtype="<f4").tobytes()


def _from_bytes(raw) -> np.ndarray:
    return np.frombuffer(bytes(raw), dtype="<f4")


def mariadb_connect():
    import pymysql
    return pymysql.connect(host=config.DB_HOST, port=config.DB_PORT, user=config.DB_USER, password=config.DB_PASSWORD,
                           database=config.DB_NAME, charset="utf8mb4", autocommit=True, connect_timeout=5)


class PlaceDB:
    def __init__(self, connect=None, embed=None, sqlite: bool = False):
        """
        Args:
            connect: DB 연결을 만드는 함수 (기본: .env 의 MariaDB)
            embed: 문장 목록 → 벡터 목록 함수. 기본은 PlaceRanker 모델 (테스트에서 가짜를 넣는다)
            sqlite: connect가 sqlite3 연결이면 True (테스트용: '?' 자리표시, 스키마 자동 생성)
        """
        self._connect = connect or mariadb_connect
        self._embed = embed
        self._sqlite = sqlite
        self._conn = None
        self._lock = threading.RLock()

    @classmethod
    def in_memory(cls, embed=None) -> "PlaceDB":
        """테스트용: 메모리 SQLite에 같은 테이블을 만든 DB"""
        import sqlite3
        conn = sqlite3.connect(":memory:", check_same_thread=False)
        conn.executescript(SQLITE_SCHEMA)
        return cls(connect=lambda: conn, embed=embed, sqlite=True)

    # ── 내부 ──────────────────────────────────────────────────────────
    def _db(self):
        if self._conn is None:
            self._conn = self._connect()
        elif not self._sqlite:
            self._conn.ping(reconnect=True)  # 오래 쉬어 끊긴 연결은 다시 잇는다
        return self._conn

    def _sql(self, sql: str) -> str:
        return sql.replace("%s", "?") if self._sqlite else sql

    def _run(self, sql: str, params=(), many: bool = False):
        with self._lock:
            conn = self._db()
            cur = conn.cursor()
            try:
                (cur.executemany if many else cur.execute)(self._sql(sql), params)
                rows = cur.fetchall() if cur.description else []
            finally:
                cur.close()
            if self._sqlite:
                conn.commit()
            return rows

    def _in(self, sql: str, ids: list[str], extra=()) -> list:
        """WHERE … IN (…) 를 id 묶음별로 나눠 실행"""
        out = []
        for s in range(0, len(ids), _CHUNK):
            part = ids[s:s + _CHUNK]
            out += self._run(sql.replace("(?)", "(" + ",".join(["%s"] * len(part)) + ")"), (*extra, *part))
        return out

    def _embed_texts(self, texts: list[str]):
        if self._embed is None:
            from travel.embeddings import get_ranker
            return get_ranker().embed_texts(texts)
        return self._embed(texts)

    def _time_param(self, dt: datetime):
        return dt.isoformat(sep=" ") if self._sqlite else dt

    @staticmethod
    def _as_datetime(v) -> datetime | None:
        if v is None:
            return None
        return v if isinstance(v, datetime) else datetime.fromisoformat(str(v))

    # ── 지역 상태 ─────────────────────────────────────────────────────
    def region_age_days(self, regn: str, signgu: str) -> float | None:
        """그 시군구를 저장한 지 며칠 됐는지. 저장한 적 없으면 None."""
        rows = self._run("SELECT fetched_at FROM tour_region WHERE regn_cd=%s AND signgu_cd=%s", (regn, signgu))
        t = self._as_datetime(rows[0][0]) if rows else None
        return None if t is None else (datetime.now() - t).total_seconds() / 86400

    def is_fresh(self, regn: str, signgu: str) -> bool:
        age = self.region_age_days(regn, signgu)
        return age is not None and age < config.PLACE_DB_MAX_AGE_DAYS

    def set_region_time(self, regn: str, signgu: str, when: datetime) -> None:
        self._run("REPLACE INTO tour_region (regn_cd, signgu_cd, fetched_at) VALUES (%s, %s, %s)",
                  (regn, signgu, self._time_param(when)))

    # ── 저장 ──────────────────────────────────────────────────────────
    def put_region(self, regn: str, signgu: str, places: list[dict], sido_of) -> int:
        """
        한 시군구의 장소를 통째로 저장합니다. 그 시군구에 있었지만 이번 목록에 없는 장소(폐업 등)는 지웁니다.
        sido_of(place) → 그 장소의 시도 이름 (문장을 만들 때 씀)
        Returns: 저장한 장소 수
        """
        from travel.documents import place_text
        from travel.places import is_indoor

        rows = {}
        for p in places:
            cid = str(p.get("content_id") or "")
            if not cid or not p.get("title") or str(p.get("content_type_id")) in SKIP_TYPES:
                continue
            rows[cid] = p
        with self._lock:
            old = dict(self._run("SELECT content_id, text_hash FROM tour_place WHERE regn_cd=%s AND signgu_cd=%s",
                                 (regn, signgu)))
            gone = [i for i in old if i not in rows]
            if gone:
                self._in("DELETE FROM tour_place WHERE content_id IN (?)", gone)

            fresh, same = [], []
            for cid, p in rows.items():
                sido = sido_of(p)
                text = place_text(p, sido)
                th = text_hash(text)
                data = _slim(p)
                data["indoor"] = bool(p.get("indoor", is_indoor(p)))
                meta = (regn, signgu, sido, str(p.get("content_type_id", "")), data["indoor"], text, th,
                        json.dumps(data, ensure_ascii=False))
                (same if old.get(cid) == th else fresh).append((cid, meta))

            # 문장이 그대로인 장소는 벡터를 다시 계산하지 않는다 (정보만 갱신)
            if same:
                self._run("UPDATE tour_place SET regn_cd=%s, signgu_cd=%s, sido=%s, type_id=%s, indoor=%s, doc_text=%s, "
                          "text_hash=%s, data=%s WHERE content_id=%s", [(*m, cid) for cid, m in same], many=True)
            if fresh:
                embs = self._embed_texts([m[5] for _, m in fresh])
                self._run("REPLACE INTO tour_place (content_id, regn_cd, signgu_cd, sido, type_id, indoor, doc_text, "
                          "text_hash, data, embedding) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                          [(cid, *m, _to_bytes(e)) for (cid, m), e in zip(fresh, embs)], many=True)
            self.set_region_time(regn, signgu, datetime.now())
        return len(rows)

    def refresh_texts(self, ids: list[str] | None = None, batch: int = 2000, progress=None) -> int:
        """
        저장된 장소의 문장을 지금 규칙(place_text)으로 다시 만들고, 바뀐 것만 벡터를 다시 계산합니다.
        TourAPI는 부르지 않습니다. (분류 이름·소개글을 문장에 넣도록 바꾼 뒤, 받아 둔 소개글이 늘었을 때)
        Returns: 벡터를 다시 계산한 장소 수
        """
        from travel.documents import place_text

        all_ids = list(dict.fromkeys(ids)) if ids is not None else [r[0] for r in self._run("SELECT content_id FROM tour_place")]
        changed = 0
        for s in range(0, len(all_ids), batch):
            part = all_ids[s:s + batch]
            todo = []
            for cid, sido, th, data in self._in("SELECT content_id, sido, text_hash, data FROM tour_place WHERE content_id IN (?)", part):
                try:
                    text = place_text(json.loads(data), sido)
                except Exception:
                    continue
                if text_hash(text) != th:
                    todo.append((cid, text))
            if todo:
                embs = self._embed_texts([t for _, t in todo])
                self._run("UPDATE tour_place SET doc_text=%s, text_hash=%s, embedding=%s WHERE content_id=%s",
                          [(t, text_hash(t), _to_bytes(e), cid) for (cid, t), e in zip(todo, embs)], many=True)
                changed += len(todo)
            if progress:
                progress(min(s + batch, len(all_ids)), len(all_ids))
        return changed

    def missing_overview_ids(self, types: tuple[str, ...], regn: str | None = None) -> list[str]:
        """소개글을 아직 안 받은 장소 id (types 순서대로, 사진 있는 장소 먼저 = 대체로 유명한 곳)"""
        from collectors.tourism import cached_overview

        out = []
        for t in types:
            sql, params = "SELECT content_id, data FROM tour_place WHERE type_id=%s", [t]
            if regn:
                sql, params = sql + " AND regn_cd=%s", params + [regn]
            rows = [(not (json.loads(d).get("image") or ""), cid) for cid, d in self._run(sql, params) if not cached_overview(cid)]
            out += [cid for _, cid in sorted(rows)]
        return out

    # ── 조회 ──────────────────────────────────────────────────────────
    def get_places(self, regn: str, signgu: str | None = None, types: set[str] | None = None,
                   sido: str | None = None) -> list[dict]:
        """저장된 장소 목록 (TourAPI가 주는 것과 같은 모양). 최근 수정순."""
        sql, params = "SELECT data FROM tour_place WHERE regn_cd=%s", [regn]
        if sido:
            sql, params = sql + " AND sido=%s", params + [sido]
        if signgu is not None:
            sql, params = sql + " AND signgu_cd=%s", params + [signgu]
        if types:
            ts = sorted(types)
            sql, params = sql + " AND type_id IN (" + ",".join(["%s"] * len(ts)) + ")", params + ts
        out = []
        for (data,) in self._run(sql, params):
            try:
                p = json.loads(data)
            except Exception:
                continue
            p["source"] = "tourism"
            out.append(p)
        out.sort(key=lambda p: p.get("modified_time", ""), reverse=True)
        return out

    def vectors(self, content_ids: list[str]) -> dict[str, tuple[str, np.ndarray]]:
        """{content_id: (문장 해시, 벡터)} — 저장된 장소만"""
        ids = [i for i in dict.fromkeys(content_ids) if i]
        if not ids:
            return {}
        rows = self._in("SELECT content_id, text_hash, embedding FROM tour_place WHERE content_id IN (?)", ids)
        return {cid: (th, _from_bytes(e)) for cid, th, e in rows}

    def search(self, query: str, regn: str | None = None, k: int = 10) -> list[dict]:
        """문장으로 바로 유사도 검색 (확인·디버그용). 그 지역 장소를 모두 비교하는 정확한 검색. distance는 0에 가까울수록 비슷."""
        q = np.asarray(self._embed_texts([query])[0], dtype=np.float32)
        q /= np.linalg.norm(q) or 1.0
        sql = "SELECT data, embedding FROM tour_place" + (" WHERE regn_cd=%s" if regn else "")
        rows = self._run(sql, (regn,) if regn else ())
        if not rows:
            return []
        mat = np.stack([_from_bytes(e) for _, e in rows])
        sims = mat @ q / (np.linalg.norm(mat, axis=1) + 1e-12)
        out = []
        for i in np.argsort(-sims)[:k]:
            p = json.loads(rows[i][0])
            p["distance"] = round(float(1 - sims[i]), 3)
            out.append(p)
        return out

    def stats(self) -> dict:
        places = self._run("SELECT COUNT(*) FROM tour_place")[0][0]
        regions = self._run("SELECT COUNT(*) FROM tour_region")[0][0]
        where = "sqlite(memory)" if self._sqlite else f"mariadb://{config.DB_HOST}:{config.DB_PORT}/{config.DB_NAME}"
        return {"places": places, "regions": regions, "path": where}


_db: PlaceDB | None = None
_db_lock = threading.Lock()


def get_db() -> PlaceDB | None:
    """설정에서 꺼져 있거나 DB 접속 정보가 없으면 None (그러면 TourAPI만 쓴다)"""
    if not config.PLACE_DB_ENABLED:
        return None
    global _db
    with _db_lock:
        if _db is None:
            if not config.DB_USER:
                return None
            _db = PlaceDB()
        return _db


def reset_for_tests(db: PlaceDB | None = None) -> None:
    global _db
    _db = db
