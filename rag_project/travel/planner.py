"""
여행 일정(플랜) 생성의 순수 로직. 외부 호출 없이 입력 → 출력만 다룹니다.

- PLAN_SYSTEM_PROMPT / build_plan_user_message : LLM에 보낼 프롬프트
- normalize_plan   : LLM 응답 검증 (없는 장소 제거, 중복 제거, 날짜 맞추기)
- fallback_plan    : LLM이 실패해도 날씨·미세먼지를 반영해 만드는 기본 일정
- hydrate_plan     : 후보 id를 실제 장소 정보로 채움 (API/UI용 구조화 결과)
- render_markdown  : 채팅창에 보여줄 답변 (날씨/미세먼지 수치는 코드가 직접 채움)
"""
import re

from travel.conditions import display_line
from travel.schedule import build_timeline

PLAN_SYSTEM_PROMPT = """너는 한국 여행 플래너 챗봇이다. 사용자와 대화하듯 친근한 존댓말로 답한다.
[여행 조건], [일자별 컨디션], [후보 장소], [지역 이슈 뉴스]에 있는 정보만 근거로 '날짜별로 방문할 장소와 순서'를 정한다.
시각, 이동, 식사 장소는 시스템이 좌표와 음식점 데이터로 계산해서 채우므로 네가 정하거나 언급하지 마라.

규칙
1. 장소는 반드시 [후보 장소]의 id(C1, C2 ...)로만 지정한다. 목록에 없는 장소를 만들지 마라. 식사·휴식 항목은 만들지 마라.
2. 하루에 3~4곳. 같은 구(시군구)이거나 좌표가 가까운 장소끼리 묶어서 이동이 짧게 한다.
3. 같은 장소를 두 번 쓰지 않는다. 여행 기간 전체에서 후보를 골고루 분산해서 매일 다른 장소를 배치한다.
4. [일자별 컨디션]이 '실내 위주'인 날은 [실내] 후보를 중심으로, '실외 가능'인 날은 실외 후보(해변, 공원 등)를 적극 활용한다. '정보 없음'인 날은 섞는다.
5. note에는 그 장소에서 할 활동을 한 문장으로 쓴다. 후보의 소개글에 있는 내용만 쓰고, 없으면 이름과 유형에서 알 수 있는 정도로만 쓴다.
6. 이슈 뉴스의 영향을 받는 장소(관련이슈 표시)는 피하거나 note에 주의를 한 문장으로 쓴다.
7. 기온·강수확률·미세먼지 수치와 후보 id(C1 등)는 message, theme, note에 쓰지 마라.
8. 모드가 '수정'이면 [현재 일정]을 바탕으로 사용자의 요청만 반영해 days 전체를 다시 출력한다(바뀌지 않은 날도 포함).
   사용자가 일정 변경이 아니라 질문·인사·감사를 하면 days를 null로 하고 message로만 답한다.
9. 반드시 아래 JSON 형식의 순수 JSON만 출력한다. 설명이나 코드블록은 금지.

{
  "message": "대화체 2~3문장. 이번 일정의 핵심 컨셉",
  "days": [
    {"date": "YYYY-MM-DD", "theme": "그날의 한 줄 컨셉",
     "items": [{"candidate_id": "C1", "note": "한 문장 활동 설명"}]}
  ],
  "follow_up": "다음에 도와줄 수 있는 것을 묻는 한 문장"
}
"""


def build_plan_user_message(
    *, mode: str, region_label: str, start: str, end: str, n_days: int, party: str, preferences: str, avoid: str,
    condition_lines: list[str], candidate_lines: list[str], news_lines: list[str],
    current_plan_text: str, user_request: str,
) -> str:
    parts = [
        f"[모드] {mode}",
        "[여행 조건]\n"
        f"- 지역: {region_label}\n- 기간: {start} ~ {end} ({n_days}일)\n"
        f"- 동행: {party or '지정 없음'}\n- 취향: {preferences or '지정 없음'}\n- 피할 것: {avoid or '지정 없음'}",
        "[일자별 컨디션] (코드가 계산한 값이니 그대로 따를 것)\n" + "\n".join(condition_lines),
        "[후보 장소]\n" + ("\n".join(candidate_lines) if candidate_lines else "(없음)"),
        "[지역 이슈 뉴스]\n" + ("\n".join(news_lines) if news_lines else "(최근 관련 이슈 기사 없음)"),
    ]
    if current_plan_text:
        parts.append("[현재 일정]\n" + current_plan_text)
    parts.append("[사용자 요청]\n" + user_request)
    return "\n\n".join(parts)


# ── 검증 ──────────────────────────────────────────────────────────────
def _s(v) -> str:
    return str(v).strip() if v not in (None,) else ""


def normalize_plan(parsed, cand_map: dict[str, dict], dates: list[str]) -> tuple[dict | None, list[str]]:
    """
    LLM 응답을 검증·정리합니다.

    Returns:
        (plan, warnings)
        plan = {"message", "days": [{"theme","items":[{"slot","candidate_id","note"}]}] | None, "follow_up"}
        days가 None이면 일정 변경 없이 message만 있는 응답. 파싱 불가/전부 비었으면 plan 자체가 None.
    """
    warnings: list[str] = []
    if not isinstance(parsed, dict):
        return None, warnings
    message, follow = _s(parsed.get("message")), _s(parsed.get("follow_up"))
    days_raw = parsed.get("days")
    if days_raw in (None, []) or not isinstance(days_raw, list):
        return ({"message": message, "days": None, "follow_up": follow} if message else None), warnings

    used: set[str] = set()
    dropped = 0
    entries: list[tuple[str | None, dict]] = []
    for d in days_raw:
        if not isinstance(d, dict):
            continue
        items = []
        raw_items = d.get("items") if isinstance(d.get("items"), list) else []
        for it in raw_items:
            if not isinstance(it, dict):
                continue
            cid = it.get("candidate_id")
            cid = _s(cid) if cid not in (None, "", "null", "None") else None
            note, slot = _s(it.get("note")), _s(it.get("slot"))
            if cid is not None:
                if cid not in cand_map:
                    dropped += 1  # 후보에 없는 장소 = 지어낸 장소
                    continue
                if cid in used:
                    continue
                used.add(cid)
            elif not note:
                continue
            items.append({"slot": slot, "candidate_id": cid, "note": note})
            if len(items) >= 6:
                break
        dd = _s(d.get("date"))
        entries.append((dd if dd in dates else None, {"theme": _s(d.get("theme")), "items": items}))

    assigned: dict[str, dict] = {}
    leftovers: list[dict] = []
    for dd, entry in entries:
        if dd and dd not in assigned:
            assigned[dd] = entry
        else:
            leftovers.append(entry)
    days = []
    for date_ in dates:
        days.append(assigned.get(date_) or (leftovers.pop(0) if leftovers else {"theme": "", "items": []}))

    if dropped:
        warnings.append(f"AI가 후보에 없는 장소 {dropped}곳을 제안해 제외했습니다.")
    if all(not d["items"] for d in days):
        return None, warnings
    empty = sum(1 for d in days if not d["items"])
    if empty:
        warnings.append(f"{empty}일치 일정은 비어 있어요. 요청하시면 채워드릴게요.")
    return {"message": message, "days": days, "follow_up": follow}, warnings


def fallback_plan(dates: list[str], conditions: list[dict], ranked_ids: list[str], cand_map: dict[str, dict],
                  per_day: int = 3) -> dict:
    """
    LLM 없이 만드는 기본 일정. 궂은 날(실내 위주)에는 실내 후보를, 좋은 날에는 실외 후보를 먼저 배치합니다.
    """
    cond_by = {c["date"]: c for c in conditions}
    remaining = [cid for cid in ranked_ids if cid in cand_map]
    slots = ["오전", "오후", "저녁"]
    days = []
    for date_ in dates:
        bad = cond_by.get(date_, {}).get("outdoor_ok") is False
        prefer = [cid for cid in remaining if bool(cand_map[cid].get("indoor")) == bad]
        rest = [cid for cid in remaining if cid not in prefer]
        pick = (prefer + rest)[:per_day]
        for cid in pick:
            remaining.remove(cid)
        days.append({
            "theme": "실내 위주로 구성" if bad else "",
            "items": [{"slot": slots[i % len(slots)], "candidate_id": cid, "note": ""} for i, cid in enumerate(pick)],
        })
    return {
        "message": "취향과 날씨를 기준으로 가까운 장소끼리 묶어서 구성한 일정이에요.",
        "days": days,
        "follow_up": "원하시면 \"2일차는 실내로 바꿔줘\"처럼 말씀해 주세요. 바로 고쳐드릴게요.",
    }


# ── 구조화 / 렌더링 ───────────────────────────────────────────────────
_ID_RE = re.compile(r"\s*[\(\[]?\b[CN]\d{1,3}\b[\)\]]?")


def clean_text(text: str) -> str:
    """AI가 문장에 흘린 후보 id(C1, N2 등)를 지운다."""
    return re.sub(r"\s{2,}", " ", _ID_RE.sub("", text or "")).strip()


def _place_view(p: dict) -> dict:
    return {
        "name": p["title"], "type": p["content_type"], "address": p["addr"], "indoor": bool(p.get("indoor")),
        "image": p.get("image", ""), "mapx": p.get("mapx", ""), "mapy": p.get("mapy", ""),
        "content_id": p.get("content_id", ""),
    }


def hydrate_plan(plan: dict, cand_map: dict[str, dict], conditions: list[dict], restaurants: list[dict] | None = None) -> list[dict]:
    """
    일자별 시간표(장소·이동·식사)를 만들어 화면/API용 구조로 변환합니다.
    같은 음식점이 여러 날 반복되지 않도록 여행 전체에서 사용한 음식점을 기억합니다.
    """
    restaurants = restaurants or []
    used_restaurants: set[str] = set()
    out = []
    for cond, day in zip(conditions, plan["days"]):
        day_items = []
        for it in day["items"]:
            p = cand_map.get(it["candidate_id"]) if it["candidate_id"] else None
            if p:  # 후보 없는 항목(식사 등 자유 문구)은 시간표에서 시스템이 채우므로 버린다
                day_items.append({"place": p, "note": clean_text(it["note"])})
        events = []
        for e in build_timeline(day_items, restaurants, used_restaurants):
            ev = {"kind": e["kind"], "start": e["start"], "end": e["end"]}
            if e["kind"] == "visit":
                ev.update(place=_place_view(e["place"]), note=e.get("note", ""))
            elif e["kind"] == "meal":
                ev.update(label=e["label"], place=_place_view(e["place"]) if e["place"] else None)
            elif e["kind"] == "move":
                ev.update(**{"from": e["from"]["title"], "to": e["to"]["title"], "text": e["text"]})
            else:
                ev.update(text=e["text"])
            events.append(ev)
        visits = [e for e in events if e["kind"] == "visit"]
        out.append({
            "date": cond["date"], "label": cond["label"], "theme": clean_text(day["theme"]),
            "weather": cond["weather"], "air": cond["air"], "outdoor_ok": cond["outdoor_ok"],
            "bad_reasons": cond["bad_reasons"], "outdoor_count": sum(1 for v in visits if not v["place"]["indoor"]),
            "events": events,
            "items": [{"start": v["start"], "end": v["end"], "note": v["note"], "place": v["place"]} for v in visits],
        })
    return out


def _render_event(e: dict) -> list[str]:
    span = f"{e['start']} - {e['end']}"
    if e["kind"] == "visit":
        p = e["place"]
        tag = "🏠 실내" if p["indoor"] else "🌳 실외"
        note = f" — {e['note']}" if e.get("note") else ""
        lines = [f"- **{span}** | **{p['name']}** ({p['type']} · {tag}){note}"]
        if p["address"]:
            lines.append(f"  - 📍 위치: {p['address']}")
        return lines
    if e["kind"] == "meal":
        p = e.get("place")
        if p:
            lines = [f"- **{span}** | 🍽️ **{e['label']} 식사: {p['name']}**"]
            if p["address"]:
                lines.append(f"  - 📍 위치: {p['address']}")
            return lines
        return [f"- **{span}** | 🍽️ **{e['label']} 식사** — 이동 경로 근처에서 자유롭게"]
    if e["kind"] == "move":
        return [f"- 🚶 {span} | 이동: {e['from']} ➔ {e['to']} ({e['text']})"]
    return [f"- ☕ {span} | {e['text']}"]


def render_markdown(message: str, days_view: list[dict], conditions: list[dict], follow_up: str,
                    news_show: list[dict], place_label: str = "") -> str:
    """
    채팅창에 보여줄 답변. 서론·인사 없이 제목부터 시작하고, 시스템 오류·제약 문구(⚠️, API 오류 등)는 넣지 않습니다.
    (그런 정보는 개발자 정보 영역에만 표시) 날씨·미세먼지 수치는 코드가 직접 채웁니다.
    message: 일정이 없는 응답(질문에 대한 답 등)일 때만 쓰이고, 일정이 있을 때는 제목으로 대신합니다.
    """
    cond_by = {c["date"]: c for c in conditions}
    n = len(days_view)
    period = days_view[0]["label"] if n == 1 else f"{days_view[0]['label']} ~ {days_view[-1]['label']}"
    title = f"{place_label} " if place_label else ""
    lines = [f"## 📅 {title}{'당일' if n == 1 else f'{n}일 여행'} 일정 ({period})", ""]
    for i, day in enumerate(days_view, 1):
        head = f"### 📅 {i}일차 · {day['label']}"
        if day["theme"]:
            head += f" — {day['theme']}"
        lines += [head, display_line(cond_by[day["date"]], place_label)]
        if day["bad_reasons"]:
            lines.append(f"> 💡 {', '.join(day['bad_reasons'])} → 실내 위주로 구성했어요.")
            total = len(day["items"])
            if total and day["outdoor_count"] * 2 > total:
                lines.append("> 💡 이 날은 실외 일정이 많아요. 필요하면 \"이 날 실내로 바꿔줘\"라고 말씀해 주세요.")
        lines.append("")
        if not day["events"]:
            lines += ["- (이 날은 추천할 장소가 부족해요. \"이 날도 채워줘\"라고 말씀해 주세요)", ""]
        for e in day["events"]:
            lines += _render_event(e)
        lines.append("")
    if news_show:
        for n in news_show:
            lines.append(f"💡 방문 전 확인: [{n['title']}]({n['link']})")
        lines.append("")
    if clean_text(follow_up):
        lines.append(clean_text(follow_up))
    return "\n".join(lines).strip()
