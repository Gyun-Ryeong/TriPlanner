"""
여행 플래너 챗봇 화면 (Streamlit)

실행: python -m streamlit run chat_app.py
"""
import streamlit as st

from config import DEV_MODE, OLLAMA_MODEL
from travel.chat import GREETING, ChatSession, handle_message
from travel.pipeline import warm_up


@st.cache_resource
def _warm_up_once() -> bool:
    warm_up()  # 화면이 뜨자마자 임베딩 모델을 미리 로딩 (서버가 켜져 있는 동안 한 번만)
    return True


_warm_up_once()

st.set_page_config(page_title="TriPlanner 챗봇", page_icon="🧳", layout="centered",
                   menu_items={"Get help": None, "Report a bug": None, "About": None})  # 기본 메뉴 항목 숨김
st.title("🧳 TriPlanner 여행 플래너")
st.caption("한국관광공사 TourAPI 기반 여행 AI 가이드" + (f" | 개발 모드 (Ollama: {OLLAMA_MODEL})" if DEV_MODE else ""))

if "session" not in st.session_state:
    st.session_state.session = ChatSession()
    st.session_state.messages = [{"role": "assistant", "content": GREETING, "caveats": []}]

with st.sidebar:
    st.header("파악한 여행 조건")
    s = st.session_state.session.slots
    st.write(f"- 지역: {(s['region'] + ' ' + s['area']).strip() or '-'}")
    st.write(f"- 기간: {s['start_date'] or '-'} ~ {s['end_date'] or '-'}")
    st.write(f"- 동행: {s['party'] or '-'}")
    st.write(f"- 취향: {s['preferences'] or '-'}")
    st.write(f"- 피할 것: {s['avoid'] or '-'}")
    st.divider()
    # 개발 모드(.env의 DEV_MODE=on)에서만 보이는 점검용 옵션. 서비스 화면에는 나타나지 않는다.
    if DEV_MODE:
        st.caption("🛠 개발 모드가 켜져 있어요 (.env의 DEV_MODE=on)")
    show_dev = DEV_MODE and st.checkbox("디버그 정보 표시 (API 오류·소요 시간)", value=False)
    if st.button("새 대화 시작", use_container_width=True):
        st.session_state.session = ChatSession()
        st.session_state.messages = [{"role": "assistant", "content": GREETING, "caveats": []}]
        st.rerun()
    st.caption("예) \"이번 주말 부산 커플 여행\" → \"2일차는 실내로 바꿔줘\" → \"맛집도 넣어줘\"")

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if show_dev and msg.get("caveats"):
            with st.expander("🧪 디버그 정보 (개발 모드)"):
                for c in msg["caveats"]:
                    st.markdown(f"- {c}")

user_text = st.chat_input("예) 이번 주말에 부산 가려고 해요. 커플이고 바다 보면서 조용히 걷고 싶어요")
if user_text:
    st.session_state.messages.append({"role": "user", "content": user_text})
    with st.chat_message("user"):
        st.markdown(user_text)
    with st.chat_message("assistant"):
        with st.spinner("데이터를 모으고 일정을 짜는 중... (로컬 LLM이라 처음엔 1~2분 걸릴 수 있어요)"):
            res = handle_message(st.session_state.session, user_text)
        st.markdown(res["reply"])
        if show_dev and res["caveats"]:
            with st.expander("🧪 디버그 정보 (개발 모드)", expanded=res["stage"] == "planned"):
                for c in res["caveats"]:
                    st.markdown(f"- {c}")
                if res.get("timings"):
                    st.caption(f"소요 시간: {res['timings']} / AI: {res.get('llm_stats')}")
    st.session_state.messages.append({"role": "assistant", "content": res["reply"], "caveats": res["caveats"]})
    st.rerun()
