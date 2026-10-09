"""
장소 임베딩 캐시 + 유사도 순위.

예전에는 일정을 만들 때마다 후보 장소 200여 곳을 처음부터 임베딩해서 매번 십수 초가 걸렸습니다.
이제는 한 번 계산한 벡터를 파일(cache/place_embeddings.npz)에 저장해 두고, 처음 보는 장소만 새로 계산합니다.
질문(취향 문장) 하나만 임베딩해서 코사인 유사도로 순위를 매기므로 두 번째부터는 거의 즉시 끝납니다.
"""
import hashlib
import os
import threading
from pathlib import Path

import numpy as np

from config import EMBED_CACHE_PATH, EMBEDDING_MODEL_NAME


class PlaceRanker:
    def __init__(self, model_name: str = EMBEDDING_MODEL_NAME, cache_path: str = EMBED_CACHE_PATH):
        self._model_name = model_name
        self._path = Path(cache_path)
        self._model = None
        self._vecs: dict[str, np.ndarray] = {}
        self._cache_loaded = False
        self._lock = threading.RLock()

    # ── 모델 / 캐시 ─────────────────────────────────────────────────
    def _load_model(self) -> None:
        if self._model is None:
            from sentence_transformers import SentenceTransformer  # 무거워서 필요할 때만 import
            self._model = SentenceTransformer(self._model_name)

    def _embed(self, texts: list[str]) -> np.ndarray:
        self._load_model()
        vecs = self._model.encode(texts, normalize_embeddings=True, batch_size=64, show_progress_bar=False)
        return np.asarray(vecs, dtype=np.float32)

    def _load_cache(self) -> None:
        if self._cache_loaded:
            return
        self._cache_loaded = True
        try:
            if self._path.exists():
                data = np.load(self._path, allow_pickle=False)
                if str(data["model"]) == self._model_name:  # 모델이 바뀌면 벡터를 쓸 수 없다
                    self._vecs = {k: data["vecs"][i] for i, k in enumerate(data["keys"].tolist())}
        except Exception:
            self._vecs = {}

    def _save_cache(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            keys = list(self._vecs)
            tmp = self._path.with_suffix(".tmp.npz")
            np.savez_compressed(tmp, keys=np.array(keys), vecs=np.stack([self._vecs[k] for k in keys]),
                                model=np.array(self._model_name))
            os.replace(tmp, self._path)
        except Exception:
            pass  # 저장 실패는 다음 실행에서 다시 계산하면 되므로 무시

    def load(self) -> None:
        """모델과 캐시를 미리 올려둡니다 (첫 요청이 기다리지 않도록)."""
        with self._lock:
            self._load_cache()
            self._load_model()

    # ── 순위 ────────────────────────────────────────────────────────
    def rank(self, items: list[tuple[str, str]], query: str) -> list[str]:
        """
        Args:
            items: [(장소 id, 장소 설명 문장), ...]
            query: 취향 문장
        Returns:
            id 리스트 (유사도 높은 순)
        """
        if not items:
            return []
        with self._lock:
            self._load_cache()
            # 문장이 바뀌면(예: 소개글 추가) 다시 계산되도록 키에 문장 해시를 넣는다
            keyed = [(f"{i}|{hashlib.sha1(t.encode('utf-8')).hexdigest()[:10]}", i, t) for i, t in items]
            missing = [(k, t) for k, _, t in keyed if k not in self._vecs]
            if missing:
                for (k, _), v in zip(missing, self._embed([t for _, t in missing])):
                    self._vecs[k] = v
                self._save_cache()
            q = self._embed([query])[0]
            scores = np.stack([self._vecs[k] for k, _, _ in keyed]) @ q
            return [keyed[i][1] for i in np.argsort(-scores, kind="stable")]


_ranker: PlaceRanker | None = None
_ranker_lock = threading.Lock()


def get_ranker() -> PlaceRanker:
    """프로세스 안에서 하나만 만들어 재사용합니다."""
    global _ranker
    with _ranker_lock:
        if _ranker is None:
            _ranker = PlaceRanker()
        return _ranker
