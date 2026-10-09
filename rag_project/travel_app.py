"""
여행지 추천 RAG 테스트 화면 (Streamlit)

실행: streamlit run travel_app.py
"""
from datetime import date, timedelta

import streamlit as st

from config import DEV_MODE, OLLAMA_MODEL
from llm.ollama_client import OllamaConnectionError
from travel.pipeline import recommend_trip
from travel.regions import SIDO

LEVEL_LABEL = {"high": "🔴 높음", "medium": "🟠 보통", "low": "🟡 낮음"}

st.set_page_config(page_title="TriPlanner 여행지 추천", page_icon="✈️", layout="centered")
st.title("✈️ TriPlanner 여행지 추천")
st.caption(f"실시간 뉴스·공공데이터 반영 | 로컬 LLM: Ollama ({OLLAMA_MODEL})")

with st.form("trip"):
    c1, c2 = st.columns(2)
    region = c1.selectbox("지역(시도)", list(SIDO), index=list(SIDO).index("부산"))
    area = c2.text_input("세부 지역 (선택)", placeholder="예: 해운대, 경주")
    dates = st.date_input("여행 기간", value=(date.today() + timedelta(days=1), date.today() + timedelta(days=2)))
    c3, c4 = st.columns(2)
    party = c3.selectbox("동행", ["", "혼자", "커플", "친구", "아이 동반 가족", "부모님과 함께"])
    top_n = c4.slider("추천 개수", 1, 10, 5)
    preferences = st.text_area("취향/요청", placeholder="예: 조용한 바다 산책, 사진 찍기 좋은 곳, 비 오면 실내 위주")
    submitted = st.form_submit_button("추천 받기", use_container_width=True)

if submitted:
    if not isinstance(dates, (tuple, list)) or len(dates) != 2:
        st.warning("여행 기간의 시작일과 종료일을 모두 선택해주세요.")
        st.stop()
    with st.spinner("관광정보 · 뉴스 · 날씨를 모으고 추천을 만드는 중... (로컬 LLM이라 첫 응답은 느릴 수 있어요)"):
        try:
            res = recommend_trip(region, dates[0], dates[1], preferences=preferences,
                                 area=area.strip(), party=party, top_n=top_n)
        except (ValueError, OllamaConnectionError) as e:
            st.error(str(e))
            st.stop()

    st.subheader("요약")
    st.write(res["summary"])

    if res["risks"]:
        st.subheader("⚠️ 여행 전 확인할 이슈")
        for r in res["risks"]:
            with st.container(border=True):
                st.markdown(f"**{LEVEL_LABEL.get(r['level'], r['level'])}** · {r['category']} · {r['pub_date']}")
                st.markdown(f"[{r['title']}]({r['link']})")
                if r["detail"]:
                    st.write(r["detail"])

    if res["weather"]:
        st.subheader(f"🌤 날씨 ({res['weather_city']} 기준)")
        for d in res["weather"]:
            t = f"{d['tmin']:.0f}~{d['tmax']:.0f}℃" if d["tmin"] is not None and d["tmax"] is not None else "-"
            st.write(f"{d['date']} · {t} · 강수확률 {d['pop_max']}% · {d['sky']} · 강수 {d['precip']}")

    st.subheader("추천 여행지")
    if not res["recommendations"]:
        st.info("추천할 장소를 찾지 못했어요. 아래 제약사항을 확인해주세요.")
    for r in res["recommendations"]:
        with st.container(border=True):
            cols = st.columns([1, 3]) if r["image"] else [None, st.container()]
            if r["image"]:
                cols[0].image(r["image"], use_container_width=True)
            body = cols[1]
            body.markdown(f"**{r['rank']}. {r['name']}** · {r['type']}")
            body.caption(r["address"] or "주소 정보 없음")
            body.write(r["reason"])
            if r["risk_note"]:
                body.warning(r["risk_note"])

    if DEV_MODE:  # 내부 정보는 개발 모드에서만
        with st.expander("🛠 개발자 정보 (제약사항·한계)", expanded=True):
            for c in res["caveats"]:
                st.markdown(f"- {c}")
    st.caption("참고 데이터: " + ", ".join(res["used_sources"]) +
               f" | 후보 {res['meta']['candidates']}곳 중 {res['meta'].get('retrieved', 0)}곳 검토")
