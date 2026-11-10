"""
임베딩 모델을 PyTorch 없이 ONNX Runtime으로 돌립니다 (메모리 절약).

sentence-transformers(PyTorch)와 같은 모델·같은 계산(평균 풀링 + 정규화)이라 벡터가 사실상 같습니다.
→ 이미 만든 벡터 DB를 다시 만들 필요가 없습니다.
처음 한 번 허깅페이스에서 onnx/model.onnx 를 내려받습니다 (약 470MB, 이후 재사용).
"""
import numpy as np


class OnnxEmbedder:
    def __init__(self, model_name: str, max_len: int = 128):
        from huggingface_hub import hf_hub_download
        import onnxruntime as ort
        from tokenizers import Tokenizer

        repo = model_name if "/" in model_name else f"sentence-transformers/{model_name}"
        model_path = hf_hub_download(repo, "onnx/model.onnx")
        self._tok = Tokenizer.from_file(hf_hub_download(repo, "tokenizer.json"))
        self._tok.enable_truncation(max_len)
        pad = self._tok.token_to_id("<pad>")
        self._tok.enable_padding(pad_id=pad if pad is not None else 0, pad_token="<pad>")
        opts = ort.SessionOptions()
        opts.enable_cpu_mem_arena = False  # 큰 묶음을 처리한 뒤에도 메모리를 붙잡고 있지 않게
        self._sess = ort.InferenceSession(model_path, opts, providers=["CPUExecutionProvider"])
        self._inputs = {i.name for i in self._sess.get_inputs()}

    def encode(self, texts: list[str], batch_size: int = 64, normalize_embeddings: bool = True, **_ignored) -> np.ndarray:
        out = []
        for s in range(0, len(texts), batch_size):
            enc = self._tok.encode_batch(list(texts[s:s + batch_size]))
            ids = np.array([e.ids for e in enc], dtype=np.int64)
            mask = np.array([e.attention_mask for e in enc], dtype=np.int64)
            feed = {"input_ids": ids, "attention_mask": mask}
            if "token_type_ids" in self._inputs:
                feed["token_type_ids"] = np.zeros_like(ids)
            tokens = self._sess.run(None, feed)[0]  # (문장 수, 토큰 수, 384)
            m = mask[..., None].astype(np.float32)
            vec = (tokens * m).sum(axis=1) / np.clip(m.sum(axis=1), 1e-9, None)  # 평균 풀링
            if normalize_embeddings:
                vec = vec / np.clip(np.linalg.norm(vec, axis=1, keepdims=True), 1e-12, None)
            out.append(vec.astype(np.float32))
        return np.concatenate(out) if out else np.zeros((0, 384), dtype=np.float32)
