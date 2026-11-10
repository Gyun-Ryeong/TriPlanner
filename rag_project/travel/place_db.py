"""
장소 벡터 DB (ChromaDB, 디스크 저장).

전국 관광지·음식점 등을 미리 저장해 두고, 일정을 짤 때 TourAPI를 부르지 않고 여기서 꺼내 씁니다.
- 채우는 방법 1: build_vector_db.py 로 미리 전국(또는 원하는 시도)을 넣는다.
- 채우는 방법 2: DB에 없는 지역을 누가 물어보면 TourAPI로 받은 결과를 그대로 저장한다 (쓰면서 채워짐).

저장 단위는 TourAPI 호출 단위와 같은 '법정동 시도 코드 + 시군구 코드'입니다.
지역마다 언제 저장했는지 기록해 두고(regions.json), PLACE_DB_MAX_AGE_DAYS가 지나면 다시 받아 새로 고칩니다.
축제(15)는 날짜가 자주 바뀌어 저장하지 않고 계속 실시간으로 받습니다.

한 장소 = 한 문서
- id        : TourAPI content_id
- document  : place_text() 문장 (유사도 검색에 쓰는 그 문장)
- embedding : 그 문장의 벡터 (PlaceRanker와 같은 모델)
- metadata  : regn(시도 코드), signgu(시군구 코드), sido, type, indoor, th(문장 해시), data(장소 정보 JSON)
"""
import hashlib
import json
import os
import threading
import time
from pathlib import Path

import config

COLLECTION = "places"
SKIP_TYPES = {"15"}  # 축제·행사는 저장하지 않는다
_RAW_KEYS = ("lclsSystm1", "lclsSystm2", "lclsSystm3", "tel")  # 원본 응답 중 다른 기능이 쓰는 값만 남긴다


def text_hash(text: str) -> str:
    """PlaceRanker의 캐시 키와 같은 방식 (같은 문장이면 같은 벡터를 재사용)"""
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]


def _slim(place: dict) -> dict:
    p = {k: v for k, v in place.items() if k not in ("raw", "nearby", "issue", "issues")}
    p["raw"] = {k: (place.get("raw") or {}).get(k, "") for k in _RAW_KEYS}
    return p


class PlaceDB:
    def __init__(self, path: str | None = None, embed=None):
        """
        Args:
            path: DB 폴더 (기본 CHROMA_PERSIST_DIR)
            embed: 문장 목록 → 벡터 목록 함수. 기본은 PlaceRanker 모델 (테스트에서 가짜를 넣는다)
        """
        self.path = Path(path or config.CHROMA_PERSIST_DIR)
        self._embed = embed
        self._col = None
        self._lock = threading.RLock()
        self._regions_path = self.path / "regions.json"
        self._regions: dict[str, float] | None = None

    # ── 내부 ──────────────────────────────────────────────────────────
    def _collection(self):
        if self._col is None:
            import chromadb  # 무거워서 쓸 때만 불러온다
            self.path.mkdir(parents=True, exist_ok=True)
            client = chromadb.PersistentClient(path=str(self.path))
            # 벡터를 직접 넣으므로 embedding_function 은 쓰지 않는다. 정규화된 벡터라 cosine 거리
            self._col = client.get_or_create_collection(COLLECTION, embedding_function=None,
                                                        metadata={"hnsw:space": "cosine"})
        return self._col

    def _embed_texts(self, texts: list[str]):
        if self._embed is None:
            from travel.embeddings import get_ranker
            return get_ranker().embed_texts(texts)
        return self._embed(texts)

    def _load_regions(self) -> dict[str, float]:
        if self._regions is None:
            try:
                self._regions = json.loads(self._regions_path.read_text(encoding="utf-8"))
            except Exception:
                self._regions = {}
        return self._regions

    def _save_regions(self) -> None:
        tmp = self._regions_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._regions, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self._regions_path)

    @staticmethod
    def _key(regn: str, signgu: str) -> str:
        return f"{regn}|{signgu}"

    # ── 지역 상태 ─────────────────────────────────────────────────────
    def region_age_days(self, regn: str, signgu: str) -> float | None:
        """그 시군구를 저장한 지 며칠 됐는지. 저장한 적 없으면 None."""
        with self._lock:
            t = self._load_regions().get(self._key(regn, signgu))
        return None if t is None else (time.time() - t) / 86400

    def is_fresh(self, regn: str, signgu: str) -> bool:
        age = self.region_age_days(regn, signgu)
        return age is not None and age < config.PLACE_DB_MAX_AGE_DAYS

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
            col = self._collection()
            old = col.get(where={"$and": [{"regn": regn}, {"signgu": signgu}]}, include=["metadatas"])
            old_hash = {i: m.get("th") for i, m in zip(old["ids"], old["metadatas"])}
            gone = [i for i in old_hash if i not in rows]
            if gone:
                col.delete(ids=gone)

            ids, docs, metas, need = [], [], [], []
            for cid, p in rows.items():
                sido = sido_of(p)
                text = place_text(p, sido)
                th = text_hash(text)
                data = _slim(p)
                data["indoor"] = bool(p.get("indoor", is_indoor(p)))
                ids.append(cid)
                docs.append(text)
                metas.append({"regn": regn, "signgu": signgu, "sido": sido, "type": str(p.get("content_type_id", "")),
                              "indoor": data["indoor"], "th": th, "mt": str(p.get("modified_time", "")),
                              "data": json.dumps(data, ensure_ascii=False)})
                need.append(old_hash.get(cid) != th)

            if ids:
                # 문장이 그대로인 장소는 벡터를 다시 계산하지 않는다
                same = [i for i, n in zip(ids, need) if not n]
                kept = {}
                if same:
                    got = col.get(ids=same, include=["embeddings"])
                    kept = {i: list(e) for i, e in zip(got["ids"], got["embeddings"])}
                todo = [d for d, n in zip(docs, need) if n]
                fresh = iter(self._embed_texts(todo)) if todo else iter(())
                embs = [list(map(float, next(fresh))) if n else kept[i] for i, n in zip(ids, need)]
                for s in range(0, len(ids), 1000):  # 한 번에 너무 많이 넣으면 chroma가 거절한다
                    col.upsert(ids=ids[s:s + 1000], documents=docs[s:s + 1000],
                               metadatas=metas[s:s + 1000], embeddings=embs[s:s + 1000])

            self._load_regions()[self._key(regn, signgu)] = time.time()
            self._save_regions()
        return len(ids)

    # ── 조회 ──────────────────────────────────────────────────────────
    def get_places(self, regn: str, signgu: str | None = None, types: set[str] | None = None,
                   sido: str | None = None) -> list[dict]:
        """저장된 장소 목록 (TourAPI가 주는 것과 같은 모양). 최근 수정순."""
        conds = [{"regn": regn}]
        if sido:
            conds.append({"sido": sido})
        if signgu is not None:
            conds.append({"signgu": signgu})
        if types:
            conds.append({"type": {"$in": sorted(types)}})
        where = conds[0] if len(conds) == 1 else {"$and": conds}
        with self._lock:
            got = self._collection().get(where=where, include=["metadatas"])
        out = []
        for m in got["metadatas"]:
            try:
                p = json.loads(m["data"])
            except Exception:
                continue
            p["source"] = "tourism"
            out.append(p)
        out.sort(key=lambda p: p.get("modified_time", ""), reverse=True)
        return out

    def vectors(self, content_ids: list[str]) -> dict[str, tuple[str, list[float]]]:
        """{content_id: (문장 해시, 벡터)} — 저장된 장소만"""
        ids = [i for i in dict.fromkeys(content_ids) if i]
        if not ids:
            return {}
        with self._lock:
            got = self._collection().get(ids=ids, include=["embeddings", "metadatas"])
        return {i: (m.get("th", ""), e) for i, e, m in zip(got["ids"], got["embeddings"], got["metadatas"])}

    def search(self, query: str, regn: str | None = None, k: int = 10) -> list[dict]:
        """문장으로 바로 유사도 검색 (확인·디버그용). 결과에 distance(0에 가까울수록 비슷) 포함."""
        q = list(map(float, self._embed_texts([query])[0]))
        with self._lock:
            col = self._collection()
            res = col.query(query_embeddings=[q], n_results=k, where={"regn": regn} if regn else None,
                            include=["metadatas", "distances"])
        out = []
        for m, d in zip(res["metadatas"][0], res["distances"][0]):
            p = json.loads(m["data"])
            p["distance"] = round(float(d), 3)
            out.append(p)
        return out

    def stats(self) -> dict:
        with self._lock:
            col = self._collection()
            return {"places": col.count(), "regions": len(self._load_regions()), "path": str(self.path)}


_db: PlaceDB | None = None
_db_lock = threading.Lock()


def get_db() -> PlaceDB | None:
    """설정에서 꺼져 있으면 None (그러면 지금처럼 TourAPI만 쓴다)"""
    if not config.PLACE_DB_ENABLED:
        return None
    global _db
    with _db_lock:
        if _db is None:
            _db = PlaceDB()
        return _db


def reset_for_tests(db: PlaceDB | None = None) -> None:
    global _db
    _db = db
