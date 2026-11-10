"""임베딩 방식 선택 (onnx 먼저, 실패하면 PyTorch) — 실제 모델은 올리지 않는다"""
import sys
import types
import unittest
from unittest.mock import patch

from travel import embeddings
from travel.embeddings import PlaceRanker


class BackendTests(unittest.TestCase):
    def test_uses_onnx_when_available(self):
        fake = types.SimpleNamespace(OnnxEmbedder=lambda name: ("onnx", name))
        with patch.object(embeddings, "EMBEDDING_BACKEND", "onnx"), patch.dict(sys.modules, {"travel.onnx_embedder": fake}):
            r = PlaceRanker(cache_path="none.npz")
            r._load_model()
        self.assertEqual(r._model[0], "onnx")

    def test_falls_back_to_torch_when_onnx_fails(self):
        def broken(name):
            raise OSError("내려받기 실패")

        onnx = types.SimpleNamespace(OnnxEmbedder=broken)
        st = types.SimpleNamespace(SentenceTransformer=lambda name: ("torch", name))
        with patch.object(embeddings, "EMBEDDING_BACKEND", "onnx"), \
             patch.dict(sys.modules, {"travel.onnx_embedder": onnx, "sentence_transformers": st}):
            r = PlaceRanker(cache_path="none.npz")
            r._load_model()
        self.assertEqual(r._model[0], "torch")

    def test_torch_setting_skips_onnx(self):
        onnx = types.SimpleNamespace(OnnxEmbedder=lambda name: self.fail("onnx를 쓰면 안 됨"))
        st = types.SimpleNamespace(SentenceTransformer=lambda name: ("torch", name))
        with patch.object(embeddings, "EMBEDDING_BACKEND", "torch"), \
             patch.dict(sys.modules, {"travel.onnx_embedder": onnx, "sentence_transformers": st}):
            r = PlaceRanker(cache_path="none.npz")
            r._load_model()
        self.assertEqual(r._model[0], "torch")


if __name__ == "__main__":
    unittest.main()
