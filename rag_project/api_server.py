"""
TriPlanner RAG 서버 (FastAPI)

Spring Boot 백엔드나 React 프론트에서 HTTP로 호출하는 용도입니다.

실행:  uvicorn api_server:app --port 8000
문서:  http://localhost:8000/docs  (Swagger UI에서 바로 테스트 가능)
"""
import threading
import time
from datetime import date

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from config import DEV_MODE, NEWS_DAYS_BACK, OLLAMA_MODEL
from llm.ollama_client import OllamaConnectionError
from travel.chat import GREETING, ChatSession, handle_message
from travel.pipeline import recommend_trip, warm_up
from travel.regions import SIDO, normalize_region
from travel.risk_scanner import scan_regional_risks

app = FastAPI(title="TriPlanner RAG API", version="0.1.0")

# 프론트(React)에서 직접 호출할 때를 위한 CORS. 배포 시에는 실제 주소로 좁히세요.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class RecommendRequest(BaseModel):
    region: str = Field(..., description="시도명 (예: 부산, 제주, 서울)", examples=["부산"])
    area: str = Field("", description="시군구 등 세부 지역 (선택)", examples=["해운대"])
    start_date: date = Field(..., description="여행 시작일 (YYYY-MM-DD)")
    end_date: date = Field(..., description="여행 종료일 (YYYY-MM-DD)")
    preferences: str = Field("", description="취향/요청 자유 텍스트", examples=["조용한 바다 산책, 사진 찍기 좋은 곳"])
    party: str = Field("", description="동행 (예: 커플, 아이 동반 가족)", examples=["커플"])
    top_n: int = Field(5, ge=1, le=10, description="추천 개수")


@app.on_event("startup")
def _startup() -> None:
    warm_up()  # 임베딩 모델을 미리 올려 첫 요청이 느려지지 않게 함


# ── 대화형 플래너 ─────────────────────────────────────────────────────
# 세션은 서버 메모리에 보관합니다(서버를 재시작하면 대화가 사라짐). 여러 서버로 늘릴 때는 Redis 등으로 옮기세요.
SESSIONS: dict[str, ChatSession] = {}
SESSIONS_LOCK = threading.Lock()
SESSION_TTL_SEC = 2 * 60 * 60


class ChatRequest(BaseModel):
    session_id: str | None = Field(None, description="이전 응답의 session_id. 비우면 새 대화를 시작")
    message: str = Field("", description="사용자 메시지. 비워서 보내면 인사말을 돌려줌")
    debug: bool = Field(False, description="true면 이 응답에 caveats·timings·llm_stats 포함 (백엔드가 관리자에게만 허용)")


def _get_session(session_id: str | None) -> ChatSession:
    now = time.time()
    with SESSIONS_LOCK:
        for sid in [k for k, v in SESSIONS.items() if now - v.last_used > SESSION_TTL_SEC]:
            del SESSIONS[sid]
        if session_id and session_id in SESSIONS:
            return SESSIONS[session_id]
        sess = ChatSession()
        SESSIONS[sess.session_id] = sess
        return sess


@app.post("/chat")
def chat(req: ChatRequest):
    """
    대화로 여행 일정을 짭니다. 같은 session_id로 계속 호출하면 이전 대화를 기억합니다.

    응답: reply(마크다운 답변), stage(asking|planned), slots(파악한 조건), missing(더 필요한 정보),
          plan(일자별 일정), conditions(일자별 날씨·미세먼지), risks(이슈 뉴스), caveats(제약사항)
    """
    sess = _get_session(req.session_id)
    return handle_message(sess, req.message, debug=req.debug)


@app.delete("/chat/{session_id}")
def reset_chat(session_id: str):
    with SESSIONS_LOCK:
        SESSIONS.pop(session_id, None)
    return {"deleted": session_id}


@app.get("/health")
def health():
    return {"status": "ok", **({"model": OLLAMA_MODEL} if DEV_MODE else {})}


@app.get("/regions")
def regions():
    return {"regions": list(SIDO)}


@app.post("/recommend")
def recommend(req: RecommendRequest):
    """여행지 추천 + 리스크 + 제약사항을 한 번에 반환."""
    try:
        result = recommend_trip(
            region=req.region, start_date=req.start_date, end_date=req.end_date,
            preferences=req.preferences, area=req.area, party=req.party, top_n=req.top_n,
        )
        if not DEV_MODE:  # 서비스 응답에는 API 오류·제약사항 같은 내부 정보를 싣지 않는다
            result.pop("caveats", None)
            result.pop("meta", None)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except OllamaConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/risks")
def risks(
    region: str = Query(..., description="시도명"),
    area: str = Query("", description="세부 지역"),
    days_back: int = Query(NEWS_DAYS_BACK, ge=1, le=30),
):
    """
    지역 리스크 뉴스만 조회 (LLM 미사용, 빠름).
    저장된 일정을 주기적으로 점검해 알림을 보내는 '리스크 알림' 기능에 쓸 수 있습니다.
    """
    sido = normalize_region(region)
    if sido is None:
        raise HTTPException(status_code=400, detail=f"지원하지 않는 지역입니다: {region}")
    items, warnings = scan_regional_risks(sido, area=area, days_back=days_back)
    return {"region": sido, "area": area, "items": items, **({"warnings": warnings} if DEV_MODE else {})}
