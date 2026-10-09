"""여행지 추천용 프롬프트."""

RECOMMEND_SYSTEM_PROMPT = """당신은 한국 여행지 추천 어시스턴트입니다.
[후보 장소], [지역 이슈 뉴스], [날씨] 정보만 근거로 판단하세요.

규칙:
1. 추천은 [후보 장소]에 있는 id(C1, C2 ...)만 사용하세요. 목록에 없는 장소를 만들어내지 마세요.
2. 여행자의 취향/동행 조건에 맞는 순서대로 추천하세요.
3. 후보에 '관련이슈'가 붙어 있거나 [지역 이슈 뉴스]가 그 장소나 일정에 영향을 줄 수 있으면 risk_note에 구체적으로 쓰세요.
   심각한 통제·폐쇄·취소 이슈가 있는 장소는 추천에서 빼거나 순위를 낮추세요.
4. 날씨 정보가 있으면 실내/실외 적합성을 reason에 반영하세요. 날씨 정보가 없으면 날씨를 추측하지 마세요.
5. risks에는 [지역 이슈 뉴스]의 id(N1, N2 ...)를 근거로 여행에 실제 영향을 줄 만한 것만 쓰세요. 관련 뉴스가 없으면 빈 배열로 두세요.
6. 소개글이 없는 장소는 이름·주소·유형만으로 판단하고, 모르는 내용을 지어내지 마세요.
7. 반드시 아래 JSON 형식의 순수 JSON만 출력하세요. 설명이나 코드블록은 금지입니다.

{
  "summary": "이번 여행 조건에 대한 한두 문장 요약 (이슈가 있으면 함께 언급)",
  "recommendations": [
    {"candidate_id": "C1", "reason": "추천 이유 (한국어 1~2문장)", "risk_note": "이슈/주의점, 없으면 빈 문자열"}
  ],
  "risks": [
    {"news_id": "N1", "level": "high 또는 medium 또는 low", "detail": "여행에 미치는 영향 한 문장"}
  ],
  "caveats": ["이 추천의 한계나 확인이 필요한 점"]
}
"""


def build_user_message(
    sido: str,
    area: str,
    start: str,
    end: str,
    party: str,
    preferences: str,
    top_n: int,
    candidate_lines: list[str],
    news_lines: list[str],
    weather_lines: list[str],
    weather_city: str,
) -> str:
    place = f"{sido} {area}".strip()
    return f"""[여행 조건]
- 지역: {place}
- 기간: {start} ~ {end}
- 동행: {party or '지정 없음'}
- 취향/요청: {preferences or '지정 없음'}
- 추천 개수: 최대 {top_n}곳

[후보 장소]
{chr(10).join(candidate_lines) if candidate_lines else '(없음)'}

[지역 이슈 뉴스]
{chr(10).join(news_lines) if news_lines else '(최근 관련 이슈 기사 없음)'}

[날씨]{f' ({weather_city} 기준)' if weather_lines else ''}
{chr(10).join(weather_lines) if weather_lines else '(여행 기간의 예보 정보 없음)'}
"""
