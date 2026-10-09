"""
로컬 Ollama 모델 호출 유틸.

- chat_json(): 시스템/유저 프롬프트를 보내고 JSON(dict)으로 파싱해서 돌려줌 (여행 추천 등에서 사용)
- ask_with_caveats(): 범용 RAG 챗봇용 (답변/제약사항 분리)

사전 준비:
  1) https://ollama.com 에서 Ollama 설치
  2) `ollama pull gemma4:26b` (또는 .env의 OLLAMA_MODEL에 지정한 다른 모델)
  3) ollama가 백그라운드에서 실행 중이어야 함 (설치하면 보통 자동 실행)
"""
import json

import requests

from config import OLLAMA_BASE_URL, OLLAMA_MODEL, OLLAMA_TIMEOUT, OLLAMA_NUM_CTX

SYSTEM_PROMPT = """당신은 한국 공공데이터와 뉴스 트렌드를 바탕으로 답변하는 어시스턴트입니다.
아래 규칙을 반드시 지키세요.

1. 제공된 [참고 문서]에 있는 정보만 근거로 답변하세요. 문서에 없는 내용은 추측하지 마세요.
2. 반드시 아래 JSON 형식으로만 응답하세요. 다른 텍스트나 설명, 마크다운 코드블록 없이 순수 JSON만 출력하세요.

{
  "answer": "질문에 대한 핵심 답변 (한국어, 자연스러운 문장)",
  "caveats": [
    "이 답변의 한계나 제약사항을 항목별로 명시 (예: 데이터 기준 시점, 조사 지역의 한계, 표본 개수 부족 등)"
  ],
  "used_sources": ["답변에 실제로 사용한 source 종류들, 예: tourism, weather, culture, air_quality, traffic, naver_news"]
}

caveats는 최소 1개 이상 반드시 포함하세요. 참고 문서가 부족하거나 오래된 경우, 특정 지역/기간에 한정된 경우를 명시하세요.
"""


class OllamaConnectionError(Exception):
    """Ollama 서버 연결 실패, 타임아웃, 모델 없음 등."""


def _post_chat(messages: list[dict], temperature: float = 0.2, json_mode: bool = True) -> str:
    payload = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
        "options": {"temperature": temperature, "num_ctx": OLLAMA_NUM_CTX},
    }
    if json_mode:
        payload["format"] = "json"  # JSON만 출력하도록 강제 (모델이 지원해야 함)

    try:
        resp = requests.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload, timeout=OLLAMA_TIMEOUT)
    except requests.exceptions.ConnectionError:
        raise OllamaConnectionError(
            f"{OLLAMA_BASE_URL}에 연결할 수 없습니다. "
            "Ollama가 실행 중인지 확인하세요 (터미널에서 `ollama serve` 또는 앱 실행)."
        )
    except requests.exceptions.Timeout:
        raise OllamaConnectionError(
            f"Ollama 응답이 {OLLAMA_TIMEOUT}초 안에 오지 않았습니다. "
            "첫 호출은 모델 로딩 때문에 오래 걸릴 수 있어요. .env의 OLLAMA_TIMEOUT을 늘려보세요."
        )

    if resp.status_code == 404:
        raise OllamaConnectionError(
            f"모델 '{OLLAMA_MODEL}'을(를) 찾을 수 없습니다. `ollama list`로 이름을 확인하고 "
            ".env의 OLLAMA_MODEL과 맞춰주세요."
        )
    if resp.status_code >= 400:
        try:
            detail = resp.json().get("error", resp.text)
        except ValueError:
            detail = resp.text
        raise OllamaConnectionError(f"Ollama 오류 {resp.status_code}: {str(detail)[:400]}")
    return resp.json().get("message", {}).get("content", "").strip()


def _parse_json(raw: str) -> dict | None:
    """모델 출력에서 JSON 객체를 최대한 복구해서 파싱. 실패하면 None."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        pass
    # 앞뒤에 설명이 붙은 경우: 첫 { 부터 마지막 } 까지 시도
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            obj = json.loads(text[start : end + 1])
            return obj if isinstance(obj, dict) else None
        except json.JSONDecodeError:
            return None
    return None


def chat_json(system_prompt: str, user_message: str, temperature: float = 0.2) -> tuple[dict | None, str]:
    """
    Returns:
        (파싱된 dict 또는 None, 모델 원문). None이면 호출한 쪽에서 폴백 처리하세요.
    """
    raw = _post_chat(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        temperature=temperature,
    )
    return _parse_json(raw), raw


def _format_context(retrieved_docs: list[dict]) -> str:
    lines = []
    for i, doc in enumerate(retrieved_docs, 1):
        lines.append(f"{i}. ({doc['metadata'].get('source', '')}) {doc['text']}")
    return "\n".join(lines) if lines else "(참고 문서 없음)"


def ask_with_caveats(question: str, retrieved_docs: list[dict]) -> dict:
    """
    범용 RAG 챗봇용.

    Returns:
        {"answer": str, "caveats": list[str], "used_sources": list[str]}
    """
    user_message = f"""[참고 문서]
{_format_context(retrieved_docs)}

[질문]
{question}"""

    parsed, raw = chat_json(SYSTEM_PROMPT, user_message)
    if parsed is None:
        parsed = {
            "answer": raw,
            "caveats": ["응답을 구조화된 형식으로 파싱하지 못했습니다. 원문을 그대로 표시합니다."],
            "used_sources": [],
        }

    parsed.setdefault("answer", "")
    parsed.setdefault("caveats", [])
    parsed.setdefault("used_sources", [])
    return parsed
