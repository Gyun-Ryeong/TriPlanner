"""
일자별 날씨·미세먼지 컨디션.

코드가 직접 계산하므로 LLM이 수치를 지어낼 수 없고, 화면에도 이 값을 그대로 보여줍니다.
"""
from datetime import date, timedelta

from travel.dates import fmt_md

BAD_GRADES = ("나쁨", "매우나쁨")
POP_RAIN = 60        # 강수확률 이 값 이상이면 비로 간주
HEAT = 33            # 최고기온 이 값 이상이면 더위 주의
COLD = -5            # 최저기온 이 값 이하이면 추위 주의


def _sky_icon(w: dict) -> str:
    precip = w.get("precip", "없음")
    if "눈" in precip:
        return "❄️"
    if precip != "없음":
        return "🌧"
    return {"맑음": "☀️", "구름많음": "⛅", "흐림": "☁️"}.get(w.get("sky", ""), "🌤")


def build_day_conditions(
    start: date, end: date, weather_days: list[dict], air_by_date: dict[str, dict]
) -> list[dict]:
    """
    Returns:
        [{"date","label","weather","air","bad_reasons","outdoor_ok","recommend"}, ...] (여행 일수만큼)
        outdoor_ok: True=실외 가능, False=실내 위주 권장, None=예보 정보 없음
    """
    w_by = {w["date"]: w for w in weather_days}
    out = []
    d = start
    while d <= end:
        key = d.isoformat()
        w, a = w_by.get(key), air_by_date.get(key)
        reasons: list[str] = []
        if w:
            if (w.get("pop_max") or 0) >= POP_RAIN or w.get("precip", "없음") != "없음":
                reasons.append("비/눈 예보")
            if w.get("tmax") is not None and w["tmax"] >= HEAT:
                reasons.append(f"더위({w['tmax']:.0f}℃)")
            if w.get("tmin") is not None and w["tmin"] <= COLD:
                reasons.append(f"추위({w['tmin']:.0f}℃)")
        if a:
            if a.get("pm10") in BAD_GRADES:
                reasons.append(f"미세먼지 {a['pm10']}")
            if a.get("pm25") in BAD_GRADES:
                reasons.append(f"초미세먼지 {a['pm25']}")
        has_data = bool(w or a)
        out.append({
            "date": key,
            "label": fmt_md(d),
            "weather": w,
            "air": a,
            "bad_reasons": reasons,
            "outdoor_ok": (not reasons) if has_data else None,
            "recommend": ("실내 위주" if reasons else "실외 가능") if has_data else "정보 없음",
        })
        d += timedelta(days=1)
    return out


def _temp_text(w: dict) -> str:
    lo, hi = w.get("tmin"), w.get("tmax")
    if lo is None or hi is None:
        return ""
    return f"{lo:.0f}℃" if round(lo) == round(hi) else f"{lo:.0f}~{hi:.0f}℃"


def season_hint(iso_date: str, place: str = "") -> str:
    """예보가 아직 없는 날은 계절에 맞는 자연스러운 안내로 대신합니다 (기온·강수 수치는 지어내지 않음)."""
    month = int(iso_date[5:7])
    of = f"{place}의 " if place else ""
    if month in (12, 1, 2):
        return f"❄️ 차분한 {of}겨울 날씨예요. 따뜻하게 입고 오세요."
    if month in (3, 4, 5):
        return f"🌸 화사한 {of}봄 날씨예요. 일교차가 있으니 가벼운 겉옷을 챙기세요."
    if month in (6, 7, 8):
        return f"☀️ 푸르른 {of}여름 날씨예요. 소나기에 대비해 우산을 챙기세요."
    return f"🍂 쾌청한 {of}가을 날씨예요. 일교차가 크니 얇은 겉옷을 챙기세요."


def display_line(c: dict, place: str = "") -> str:
    """사용자에게 보여줄 한 줄 요약 (마크다운)."""
    parts = []
    w, a = c["weather"], c["air"]
    if w:
        temp = _temp_text(w)
        pop = f"강수확률 {w['pop_max']}%" if w.get("pop_max") is not None else ""
        parts.append(" · ".join(x for x in [f"{_sky_icon(w)} {w.get('sky', '')}", temp, pop] if x.strip()))
    if a:
        dust = []
        if a.get("pm10"):
            dust.append(f"미세먼지 {a['pm10']}")
        if a.get("pm25"):
            dust.append(f"초미세먼지 {a['pm25']}")
        parts.append(f"😷 {' · '.join(dust)} ({a.get('source', '')})")
    if not parts:
        return season_hint(c["date"], place)
    return "  |  ".join(parts)


def prompt_line(c: dict) -> str:
    """LLM에 줄 한 줄. 수치는 그대로, 결론(권장)은 코드가 정해서 준다."""
    w, a = c["weather"], c["air"]
    bits = []
    if w:
        temp = f"{w['tmin']:.0f}~{w['tmax']:.0f}℃" if w.get("tmin") is not None and w.get("tmax") is not None else "기온 불명"
        bits.append(f"{w.get('sky', '')} {temp}, 강수확률 {w.get('pop_max', '?')}%, 강수 {w.get('precip', '없음')}")
    if a:
        bits.append(f"미세먼지 {a.get('pm10', '?')}, 초미세먼지 {a.get('pm25', '?')}")
    body = " / ".join(bits) if bits else "예보 정보 없음"
    why = f" (사유: {', '.join(c['bad_reasons'])})" if c["bad_reasons"] else ""
    return f"- {c['date']}({c['label'].split('(')[1][:-1]}): {body} → {c['recommend']}{why}"
