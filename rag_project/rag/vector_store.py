"""
ChromaDB + sentence-transformers를 이용한 벡터 저장소.
별도 임베딩 API 비용 없이 동작합니다.

- persist=True  : 디스크(CHROMA_PERSIST_DIR)에 저장 (기존 범용 챗봇용)
- persist=False : 메모리에만 보관 (여행 추천처럼 요청마다 쓰고 버리는 용도)
"""
import chromadb
from chromadb.utils import embedding_functions

from config import EMBEDDING_MODEL_NAME, CHROMA_PERSIST_DIR, TOP_K


class VectorStore:
    def __init__(self, collection_name: str = "public_data_rag", persist: bool = True):
        if persist:
            self._client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
        else:
            self._client = chromadb.EphemeralClient()
        self._embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=EMBEDDING_MODEL_NAME
        )
        self._collection = self._client.get_or_create_collection(
            name=collection_name, embedding_function=self._embed_fn
        )

    def add_documents(self, docs: list[dict]) -> None:
        """docs: [{"id":..., "text":..., "metadata": {...}}, ...]"""
        if not docs:
            return
        self._collection.add(
            ids=[d["id"] for d in docs],
            documents=[d["text"] for d in docs],
            metadatas=[d["metadata"] for d in docs],
        )

    def search(
        self,
        query: str,
        top_k: int = TOP_K,
        source_filter: str | None = None,
        where: dict | None = None,
    ) -> list[dict]:
        """
        Args:
            source_filter: metadata의 source 값으로 거르기 (간편 옵션)
            where: chroma where 조건 (예: {"request_id": "abc"}). source_filter보다 우선.
        """
        if where is None and source_filter:
            where = {"source": source_filter}

        # 조건에 맞는 문서 수보다 많이 요청하면 버전에 따라 오류가 날 수 있어 상한을 둠
        matched = len(self._collection.get(where=where, include=[])["ids"])
        if matched == 0:
            return []
        n_results = min(top_k, matched)

        result = self._collection.query(query_texts=[query], n_results=n_results, where=where)

        docs = []
        if result["documents"]:
            for text, meta, dist in zip(
                result["documents"][0], result["metadatas"][0], result["distances"][0]
            ):
                docs.append({"text": text, "metadata": meta, "distance": dist})
        return docs

    def delete(self, where: dict) -> None:
        """where 조건에 맞는 문서를 삭제합니다."""
        self._collection.delete(where=where)

    def clear(self) -> None:
        """컬렉션을 초기화합니다 (새 데이터로 다시 채울 때 사용)."""
        name = self._collection.name
        self._client.delete_collection(name)
        self._collection = self._client.get_or_create_collection(
            name=name, embedding_function=self._embed_fn
        )
