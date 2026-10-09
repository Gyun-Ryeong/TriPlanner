"""
공공데이터포털 API 공통 호출 유틸리티.
- 대부분의 공공데이터포털 API는 JSON/XML 둘 다 지원하는 경우가 많아
  가능하면 JSON(type=json)으로 요청하고, XML만 지원하는 API는 xmltodict로 파싱합니다.
- 인증키 오류/한도초과처럼 HTTP 200으로 오는 오류 응답도 예외로 바꿔서 알려줍니다.
"""
import time
from urllib.parse import unquote

import requests
import xmltodict

from config import PUBLIC_DATA_API_KEY


class PublicDataAPIError(Exception):
    pass


def _service_key() -> str:
    """
    공공데이터포털은 'Encoding 키'(%2B, %3D 등 포함)와 'Decoding 키' 두 가지를 줍니다.
    requests는 파라미터를 자동으로 URL 인코딩하기 때문에, Encoding 키를 그대로 넣으면
    이중 인코딩되어 인증 오류(SERVICE_KEY_IS_NOT_REGISTERED)가 납니다.
    → 항상 한 번 디코딩한 값을 넘기면 어느 키를 넣어도 동작합니다.
    """
    return unquote(PUBLIC_DATA_API_KEY.strip())


def _raise_if_error(parsed) -> None:
    """HTTP 200인데 내용이 오류인 경우(인증키 오류, 한도 초과 등)를 예외로 변환."""
    if not isinstance(parsed, dict):
        return

    # 게이트웨이 오류 (XML): <OpenAPI_ServiceResponse><cmmMsgHeader>...
    if "OpenAPI_ServiceResponse" in parsed:
        header = parsed["OpenAPI_ServiceResponse"].get("cmmMsgHeader", {}) or {}
        msg = header.get("returnAuthMsg") or header.get("errMsg") or "알 수 없는 오류"
        code = header.get("returnReasonCode", "")
        raise PublicDataAPIError(f"공공데이터포털 오류: {msg} (code={code})")

    # 일부 게이트웨이는 response 래퍼 없이 최상위에 오류를 줌: {"resultCode": "...", "resultMsg": "..."}
    if "response" not in parsed and "resultCode" in parsed:
        code = str(parsed.get("resultCode", "")).strip()
        if code not in ("00", "0000", "200"):
            raise PublicDataAPIError(f"API 오류 응답: code={code}, msg={parsed.get('resultMsg', '')}")

    # 표준 응답 헤더: response.header.resultCode / resultMsg
    resp = parsed.get("response")
    header = resp.get("header") if isinstance(resp, dict) else None
    if isinstance(header, dict):
        code = str(header.get("resultCode", "")).strip()
        msg = str(header.get("resultMsg", "")).strip()
        if code and code not in ("00", "0000"):
            normalized = msg.upper().replace(" ", "").replace("_", "")
            if "NODATA" in normalized:
                return  # 데이터 없음은 오류가 아니라 빈 결과
            raise PublicDataAPIError(f"API 오류 응답: code={code}, msg={msg}")


def call_public_api(url: str, params: dict, prefer_json: bool = True, timeout: int = 15,
                    json_params: dict | None = None, retries: int = 1) -> dict:
    """
    공공데이터포털 API를 호출하고 결과를 dict로 반환합니다.

    Args:
        url: API 엔드포인트 (config.ENDPOINTS 참고)
        params: 요청 파라미터 (serviceKey 제외)
        prefer_json: True면 type=json 파라미터를 추가해 JSON 응답 시도
        timeout: 초 단위 타임아웃
        json_params: JSON 응답을 요청하는 파라미터. 기본은 _type=json,
                     에어코리아처럼 returnType=json을 쓰는 API는 직접 지정
        retries: 시간 초과/연결 실패/서버 오류(5xx)일 때 다시 시도할 횟수
    """
    if not PUBLIC_DATA_API_KEY:
        raise PublicDataAPIError(
            "PUBLIC_DATA_API_KEY가 설정되지 않았습니다. .env 파일을 확인하세요."
        )

    request_params = {"serviceKey": _service_key(), **params}
    if prefer_json:
        for k, v in (json_params or {"_type": "json"}).items():  # 모르는 파라미터는 TourAPI가 오류로 거절하므로 _type 하나만
            request_params.setdefault(k, v)

    resp = None
    for attempt in range(retries + 1):
        try:
            resp = requests.get(url, params=request_params, timeout=timeout)
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            if attempt < retries:
                time.sleep(1.0)
                continue
            raise PublicDataAPIError(
                f"서버가 {timeout}초 안에 응답하지 않았어요({type(e).__name__}): {url.rsplit('/', 1)[-1]}. "
                "제공기관 서버가 느린 경우가 많아요. 잠시 뒤 다시 시도해 보세요."
            )
        if resp.status_code >= 500 and attempt < retries:
            time.sleep(1.0)
            continue
        break
    resp.raise_for_status()

    content_type = resp.headers.get("Content-Type", "")
    text = resp.text.strip()

    # JSON으로 왔으면 바로 파싱, 아니면 XML로 간주하고 파싱
    if "json" in content_type or text.startswith("{"):
        parsed = resp.json()
    else:
        try:
            parsed = xmltodict.parse(text)
        except Exception as e:
            raise PublicDataAPIError(f"응답 파싱 실패: {e}\n원본 응답 일부: {text[:300]}")

    _raise_if_error(parsed)
    return parsed


def extract_items(parsed: dict) -> list:
    """
    공공데이터포털 표준 응답 포맷에서 item 리스트만 뽑아내는 헬퍼.
    포맷이 기관마다 조금씩 달라서 여러 경로를 시도합니다.
    """
    # JSON 표준 포맷: response.body.items.item
    try:
        body = parsed["response"]["body"]
        items = body["items"]
        if isinstance(items, dict):
            items = items.get("item", [])
        if isinstance(items, dict):
            items = [items]
        return items or []
    except (KeyError, TypeError):
        pass

    # 일부 API는 response 래퍼 없이 바로 items를 줌
    try:
        items = parsed["items"]
        if isinstance(items, dict):
            items = items.get("item", [])
        if isinstance(items, dict):
            items = [items]
        return items or []
    except (KeyError, TypeError):
        pass

    return []
