"""
Streamlit 챗 UI.
실행: streamlit run app.py

- 사용자가 질문 입력
- 질문에 맞는 공공데이터 API + 네이버 뉴스를 호출해 벡터DB에 적재
- 벡터DB에서 관련 문서 검색 (RAG)
- Claude에게 "답변"과 "제약사항"을 분리해서 요청
- 채팅 말풍선 안에서 답변 / 제약사항을 구분된 영역으로 표시
"""
import streamlit as st

from rag.vector_store import VectorStore
from rag.pipeline import fetch_and_index
from llm.ollama_client import ask_with_caveats, OllamaConnectionError
from config import OLLAMA_MODEL

st.set_page_config(page_title="공공데이터 RAG 챗봇", page_icon="🇰🇷", layout="centered")
st.title("🇰🇷 공공데이터 + 뉴스트렌드 RAG 챗봇")
st.caption(f"로컬 LLM: Ollama ({OLLAMA_MODEL})")

# ── 세션 상태 초기화 ──────────────────────────────────────────────────
if "store" not in st.session_state:
    st.session_state.store = VectorStore()
if "messages" not in st.session_state:
    st.session_state.messages = []  # [{"role": "user"/"assistant", "answer":..., "caveats":[...]}]

# ── 사이드바: 지역 선택 ──────────────────────────────────────────────
with st.sidebar:
    st.header("설정")
    region = st.selectbox("지역", ["서울", "부산", "인천", "대구", "대전", "광주"], index=0)
    st.caption("날씨/대기질 조회에 사용됩니다.")
    if st.button("벡터DB 초기화"):
        st.session_state.store.clear()
        st.session_state.messages = []
        st.success("초기화 완료")

# ── 이전 대화 렌더링 ──────────────────────────────────────────────────
for msg in st.session_state.messages:
    if msg["role"] == "user":
        with st.chat_message("user"):
            st.write(msg["content"])
    else:
        with st.chat_message("assistant"):
            st.markdown("**답변**")
            st.write(msg["answer"])
            if msg.get("caveats"):
                with st.expander("⚠️ 제약사항 / 한계", expanded=False):
                    for c in msg["caveats"]:
                        st.markdown(f"- {c}")
            if msg.get("used_sources"):
                st.caption("참고 데이터: " + ", ".join(msg["used_sources"]))

# ── 새 질문 입력 ──────────────────────────────────────────────────────
question = st.chat_input("공공데이터/뉴스 관련 질문을 입력하세요 (예: 서울 이번주 날씨 어때?)")

if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.write(question)

    with st.chat_message("assistant"):
        with st.spinner("데이터 수집 및 답변 생성 중... (로컬 LLM이라 첫 응답은 느릴 수 있어요)"):
            fetch_and_index(question, region=region, store=st.session_state.store)
            retrieved = st.session_state.store.search(question)
            try:
                result = ask_with_caveats(question, retrieved)
            except OllamaConnectionError as e:
                st.error(str(e))
                st.stop()

        st.markdown("**답변**")
        st.write(result["answer"])
        if result["caveats"]:
            with st.expander("⚠️ 제약사항 / 한계", expanded=True):
                for c in result["caveats"]:
                    st.markdown(f"- {c}")
        if result["used_sources"]:
            st.caption("참고 데이터: " + ", ".join(result["used_sources"]))

    st.session_state.messages.append({
        "role": "assistant",
        "answer": result["answer"],
        "caveats": result["caveats"],
        "used_sources": result["used_sources"],
    })
