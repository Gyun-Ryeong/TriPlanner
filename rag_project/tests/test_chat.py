"""
대화형 여행 플래너 오프라인 테스트 (키/Ollama/인터넷/벡터DB 없이 실행).

    python -m unittest tests.test_chat -v
"""
import unittest
from datetime import date
from unittest.mock import patch

from tests.test_offline import FakeRanker, _place

TODAY = date(2026, 10, 6)  # 화요일


def body(reply: str) -> str:
    """답변에서 고정 하단 서식(🛠 개발자 정보)을 뗀 본문."""
    return reply.split("\n\n---\n🛠 개발자 정보")[0]  # (지역별 구분선 '---'과 헷갈리지 않게 제목까지 포함해서 자른다)


def _news_item(nid="N1", title="부산 태풍 특보", desc="해운대해수욕장 통제"):
    return {"id": nid, "category": "기상", "keyword": "태풍", "title": title, "description": desc,
            "link": f"http://{nid}", "pub_date": "2026-10-06 09:00"}


class RegionResolveTests(unittest.TestCase):
    def test_resolve_place(self):
        from travel.regions import resolve_place
        self.assertEqual(resolve_place("부산 해운대 가고 싶어"), ("부산", "해운대"))
        self.assertEqual(resolve_place("부산 말고 제주"), ("제주", ""))
        self.assertEqual(resolve_place("경주 갈래"), ("경북", "경주"))
        self.assertEqual(resolve_place("서울에서 부산으로"), ("부산", ""))
        self.assertEqual(resolve_place("고양이랑 갈래"), (None, ""))


class DateParseTests(unittest.TestCase):
    def p(self, text):
        from travel.dates import parse_trip_dates
        return parse_trip_dates(text, TODAY)

    def test_relative_and_weekend(self):
        self.assertEqual(self.p("이번 주말")["start"], date(2026, 10, 10))
        self.assertEqual(self.p("이번 주말")["end"], date(2026, 10, 11))
        self.assertEqual(self.p("다음 주말에 가요")["start"], date(2026, 10, 17))
        self.assertEqual(self.p("내일")["start"], date(2026, 10, 7))
        self.assertEqual(self.p("내일모레")["start"], date(2026, 10, 8))
        self.assertEqual(self.p("다음 주 금요일")["start"], date(2026, 10, 16))

    def test_ranges_do_not_double_count(self):
        r = self.p("10월 10일 ~ 10월 12일")
        self.assertEqual((r["start"], r["end"]), (date(2026, 10, 10), date(2026, 10, 12)))
        r = self.p("10/10~10/12")
        self.assertEqual((r["start"], r["end"]), (date(2026, 10, 10), date(2026, 10, 12)))
        r = self.p("12월 30일부터 1월 2일까지")
        self.assertEqual((r["start"], r["end"]), (date(2026, 12, 30), date(2027, 1, 2)))

    def test_nights(self):
        r = self.p("10월 10일부터 2박 3일")
        self.assertEqual((r["start"], r["end"], r["nights"]), (date(2026, 10, 10), None, 2))
        self.assertEqual(self.p("2박3일로 갈래")["nights"], 2)
        self.assertEqual(self.p("당일치기")["nights"], 0)
        r = self.p("오늘부터 7일")
        self.assertEqual((r["start"], r["nights"]), (date(2026, 10, 6), 6))
        r = self.p("10월 10일부터 12일까지")  # '까지'가 있으면 기간이 아니라 끝 날짜
        self.assertEqual((r["end"]), date(2026, 10, 12))

    def test_past_month_rolls_to_next_year_and_negation(self):
        self.assertEqual(self.p("3월 5일")["start"], date(2027, 3, 5))
        self.assertEqual(self.p("이번 주말 말고 다음 주말")["start"], date(2026, 10, 17))


class AirQualityTests(unittest.TestCase):
    def test_parse_and_classify(self):
        from collectors.air_quality import classify_pm10, classify_pm25, parse_inform_grade
        self.assertEqual(parse_inform_grade("서울 : 좋음,제주 : 보통, 경기북부 : 매우 나쁨"),
                         {"서울": "좋음", "제주": "보통", "경기북부": "매우나쁨"})
        self.assertEqual((classify_pm10(30), classify_pm10(81), classify_pm10(151)), ("좋음", "나쁨", "매우나쁨"))
        self.assertEqual((classify_pm25(15), classify_pm25(36)), ("좋음", "나쁨"))

    def test_forecast_uses_latest_notice_and_worst_region(self):
        from collectors.air_quality import forecast_by_date
        items = [
            {"dataTime": "2026-10-06 05시 발표", "informData": "2026-10-07", "informGrade": "서울 : 좋음,경기북부 : 보통,경기남부 : 나쁨"},
            {"dataTime": "2026-10-06 17시 발표", "informData": "2026-10-07", "informGrade": "서울 : 보통,경기북부 : 보통,경기남부 : 나쁨"},
        ]
        self.assertEqual(forecast_by_date(items, "서울"), {"2026-10-07": "보통"})  # 더 늦은 발표 사용
        self.assertEqual(forecast_by_date(items, "경기"), {"2026-10-07": "나쁨"})   # 경기는 두 권역 중 나쁜 쪽

    def test_summary_forecast_realtime_and_range(self):
        import collectors.air_quality as aq
        fc = [{"dataTime": "2026-10-06 17시 발표", "informData": d, "informGrade": "부산 : 나쁨"} for d in ("2026-10-06", "2026-10-07")]
        rt = [{"pm10": "40", "pm25": "20", "data_time": "2026-10-06 18:00"}, {"pm10": "-", "pm25": "-", "data_time": ""}]
        with patch.object(aq, "get_air_forecast", return_value=fc), patch.object(aq, "get_air_quality", return_value=rt):
            res = aq.get_air_summary("부산", date(2026, 10, 6), date(2026, 10, 8), today=TODAY)
        self.assertEqual(res["by_date"]["2026-10-07"]["pm10"], "나쁨")
        self.assertEqual(res["by_date"]["2026-10-07"]["source"], "예보")
        self.assertNotIn("2026-10-08", res["by_date"])  # 예보 범위 밖
        self.assertEqual(res["realtime"]["pm10_grade"], "보통")  # 무효값('-')은 평균에서 제외

        with patch.object(aq, "get_air_forecast", side_effect=AssertionError("범위 밖이면 호출 금지")):
            far = aq.get_air_summary("부산", date(2026, 11, 1), date(2026, 11, 3), today=TODAY)
        self.assertEqual(far["by_date"], {})

    def test_summary_failure_is_reported_not_raised(self):
        import collectors.air_quality as aq
        with patch.object(aq, "get_air_forecast", side_effect=RuntimeError("키 오류")):
            res = aq.get_air_summary("부산", date(2026, 10, 7), date(2026, 10, 7), today=TODAY)
        self.assertTrue(res["warnings"])


    def test_uses_yesterdays_notice_when_today_not_published_yet(self):
        import collectors.air_quality as aq
        yesterday = [{"dataTime": "2026-10-05 23시 발표", "informData": d, "informGrade": "부산 : 나쁨"}
                     for d in ("2026-10-06", "2026-10-07", "2026-10-08")]

        def fake(search_date, code):
            return [] if search_date == "2026-10-06" else yesterday  # 오늘(10/6) 발표는 아직 없음

        with patch.object(aq, "get_air_forecast", side_effect=fake):
            res = aq.get_air_summary("부산", date(2026, 10, 7), date(2026, 10, 8), today=TODAY)
        self.assertEqual(res["by_date"]["2026-10-07"]["pm10"], "나쁨")
        self.assertEqual(res["warnings"], [])


class ConditionTests(unittest.TestCase):
    def test_bad_weather_or_dust_means_indoor(self):
        from travel.conditions import build_day_conditions
        w = [{"date": "2026-10-07", "tmin": 14, "tmax": 21, "pop_max": 70, "precip": "비", "sky": "흐림"},
             {"date": "2026-10-08", "tmin": 14, "tmax": 22, "pop_max": 10, "precip": "없음", "sky": "맑음"},
             {"date": "2026-10-09", "tmin": 14, "tmax": 22, "pop_max": 10, "precip": "없음", "sky": "맑음"}]
        air = {"2026-10-08": {"pm10": "보통", "pm25": "나쁨", "source": "예보"}, "2026-10-09": {"pm10": "좋음", "pm25": "좋음", "source": "예보"}}
        cs = build_day_conditions(date(2026, 10, 7), date(2026, 10, 10), w, air)
        self.assertEqual([c["outdoor_ok"] for c in cs], [False, False, True, None])
        self.assertIn("초미세먼지 나쁨", cs[1]["bad_reasons"])
        self.assertEqual(cs[3]["recommend"], "정보 없음")


class PlannerTests(unittest.TestCase):
    def cand(self):
        a = _place("1", "해운대해수욕장"); a["indoor"] = False
        b = _place("2", "부산박물관", ctype="문화시설"); b["indoor"] = True
        c = _place("3", "영화의전당", ctype="문화시설"); c["indoor"] = True
        return {"C1": a, "C2": b, "C3": c}

    def test_normalize_drops_invented_duplicates_and_aligns_dates(self):
        from travel.planner import normalize_plan
        parsed = {"message": "m", "follow_up": "f", "days": [
            {"date": "2026-10-09", "theme": "t", "items": [
                {"slot": "오전", "candidate_id": "C1", "note": ""},
                {"slot": "오후", "candidate_id": "C99", "note": "지어낸 곳"},
                {"slot": "점심", "candidate_id": "null", "note": "근처 식당에서 점심"}]},
            {"date": "엉뚱한날", "theme": "", "items": [
                {"slot": "오전", "candidate_id": "C1", "note": "중복"},
                {"slot": "오후", "candidate_id": "C2", "note": ""}]}]}
        plan, warns = normalize_plan(parsed, self.cand(), ["2026-10-08", "2026-10-09"])
        self.assertEqual([it["candidate_id"] for it in plan["days"][1]["items"]], ["C1", None])  # 날짜 일치 우선
        self.assertEqual([it["candidate_id"] for it in plan["days"][0]["items"]], ["C2"])        # 중복 C1 제거
        self.assertTrue(any("후보에 없는 장소" in w for w in warns))

    def test_normalize_question_only_and_garbage(self):
        from travel.planner import normalize_plan
        plan, _ = normalize_plan({"message": "천만에요", "days": None}, self.cand(), ["2026-10-08"])
        self.assertIsNone(plan["days"])
        self.assertIsNone(normalize_plan(None, self.cand(), ["2026-10-08"])[0])
        self.assertIsNone(normalize_plan({"message": "x", "days": [{"date": "2026-10-08", "items": []}]}, self.cand(), ["2026-10-08"])[0])

    def test_fallback_puts_indoor_on_bad_days(self):
        from travel.planner import fallback_plan
        conds = [{"date": "2026-10-08", "outdoor_ok": False}, {"date": "2026-10-09", "outdoor_ok": True}]
        plan = fallback_plan(["2026-10-08", "2026-10-09"], conds, ["C1", "C2", "C3"], self.cand(), per_day=2)
        bad_day = [it["candidate_id"] for it in plan["days"][0]["items"]]
        self.assertEqual(bad_day, ["C2", "C3"])  # 비 오는 날은 실내 둘
        self.assertEqual([it["candidate_id"] for it in plan["days"][1]["items"]], ["C1"])


# ── 대화 흐름 ─────────────────────────────────────────────────────────
class ChatFlowTests(unittest.TestCase):
    PLACES = [
        _place("1", "해운대해수욕장", overview="부산 대표 해변", indoor=False),
        _place("2", "광안리해수욕장", overview="야경 명소", indoor=False),
        _place("3", "부산박물관", ctype="문화시설", addr="부산 남구", indoor=True),
        _place("4", "영화의전당", ctype="문화시설", addr="부산 해운대구", indoor=True),
    ]

    def setUp(self):
        import travel.chat as chat
        self.chat = chat
        self.raw_calls = 0
        self.llm_calls = []
        self.llm_plan = None   # 플랜 생성 호출에 줄 응답
        self.llm_extract = {}  # 슬롯 추출 호출에 줄 응답
        self.llm_fail = False

        def fake_llm(messages, temperature=0.3):
            self.llm_calls.append(messages)
            if self.llm_fail:
                raise RuntimeError("ollama down")
            if messages[0]["content"].startswith("너는 여행 플래너 챗봇의 '정보 추출기'"):
                return dict(self.llm_extract), "{}"
            return self.llm_plan, self.llm_raw

        def fake_gather(sido, area, start, end, include_food, today):
            self.raw_calls += 1
            from travel.conditions import build_day_conditions  # noqa: F401  (import 확인)
            places = [dict(p) for p in self.PLACES + list(getattr(self, "extra_places", []))]
            for p in places:
                p["related_news_ids"] = ["N1"] if p["title"] == "해운대해수욕장" else []
            return {
                "sido": sido, "area": area, "start": start.isoformat(), "end": end.isoformat(),
                "include_food": include_food, "places": places, "news": [_news_item()],
                "weather": [{"date": "2026-10-10", "tmin": 14, "tmax": 21, "pop_max": 80, "precip": "비", "sky": "흐림"},
                            {"date": "2026-10-11", "tmin": 15, "tmax": 23, "pop_max": 10, "precip": "없음", "sky": "맑음"}],
                "weather_status": "ok",
                "air": {"by_date": {"2026-10-10": {"pm10": "보통", "pm25": "보통", "source": "예보"},
                                    "2026-10-11": {"pm10": "보통", "pm25": "나쁨", "source": "예보"}}, "realtime": None, "warnings": []},
                "warnings": [], "fetched_at": __import__("time").time(),
            }

        self.llm_raw = "{}"
        self.patches = [
            patch.object(chat, "CHAT_EXTRACT_LLM_MIN_CHARS", 0),  # 기존 테스트는 AI 추출 경로를 검증 (빠른 경로는 아래 별도 테스트)
            patch.object(chat, "chat_json_messages", side_effect=fake_llm),
            patch.object(chat, "gather_raw", side_effect=fake_gather),
            patch.object(chat, "enrich", return_value=[]),
        ]
        for p in self.patches:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in self.patches])
        self.session = chat.ChatSession()
        self.ranker = FakeRanker()

    def say(self, text):
        return self.chat.handle_message(self.session, text, today=TODAY, ranker=self.ranker)

    def plan_response(self):
        return {"message": "비 오는 첫날은 실내 위주로 잡았어요.", "follow_up": "더 바꿀까요?", "days": [
            {"date": "2026-10-10", "theme": "실내 데이트", "items": [
                {"slot": "오전", "candidate_id": "C3", "note": "전시 관람"},
                {"slot": "오후", "candidate_id": "C4", "note": ""}]},
            {"date": "2026-10-11", "theme": "바다", "items": [
                {"slot": "오전", "candidate_id": "C1", "note": "산책"}]}]}

    # 1) 정보 수집 대화
    def test_asks_missing_info_one_at_a_time(self):
        r = self.say("안녕하세요")
        self.assertEqual(r["stage"], "asking")
        self.assertEqual(r["missing"], ["region", "start_date", "end_date"])
        self.assertIn("어디로", r["reply"])

        r = self.say("부산 가려고요")
        self.assertEqual(r["slots"]["region"], "부산")
        self.assertIn("언제", r["reply"])
        self.assertEqual(self.raw_calls, 0)  # 아직 외부 데이터를 모으지 않는다

        r = self.say("이번 주말에요")
        self.assertEqual((r["slots"]["start_date"], r["slots"]["end_date"]), ("2026-10-10", "2026-10-11"))
        self.assertEqual(r["stage"], "asking")
        self.assertIn("누구와", r["reply"])  # 동행/취향은 한 번만 묻는다

    def test_asks_nights_when_only_start_given(self):
        r = self.say("제주도 10월 20일에 출발해요")
        self.assertEqual(r["slots"]["end_date"], "")
        self.assertIn("몇 박", r["reply"])
        r = self.say("2박 3일이요")
        self.assertEqual(r["slots"]["end_date"], "2026-10-22")

    def test_one_message_with_everything_goes_straight_to_plan(self):
        self.llm_extract = {"party": "커플", "preferences": "조용한 바다 산책"}
        self.llm_plan = self.plan_response()
        r = self.say("이번 주말에 부산 갈래요 커플이고 조용한 바다 산책하고 싶어요")
        self.assertEqual(r["stage"], "planned")
        self.assertEqual(r["slots"]["party"], "커플")
        self.assertEqual(self.raw_calls, 1)

    # 2) 일정 생성: 날씨·미세먼지 반영
    def test_plan_reflects_weather_and_dust_in_reply(self):
        self.llm_plan = self.plan_response()
        self.say("이번 주말 부산 갈래")
        r = self.say("상관없어요")
        self.assertEqual(r["stage"], "planned")
        self.assertIn("1일차", r["reply"])
        self.assertIn("🌧 흐림 · 14~21℃ · 강수확률 80%", r["reply"])   # 수치는 코드가 채움
        self.assertIn("초미세먼지 나쁨", r["reply"])
        self.assertIn("비/눈 예보", r["reply"])                          # 1일차 사유
        self.assertIn("부산박물관", r["reply"])
        self.assertIn("🏠 실내", r["reply"])
        self.assertEqual([c["outdoor_ok"] for c in r["conditions"]], [False, False])
        self.assertIn("air_quality", r["used_sources"])
        self.assertIn("weather", r["used_sources"])
        # 일정을 물었으니 뉴스는 답변에 붙이지 않는다 (데이터는 risks 필드로만 전달)
        self.assertNotIn("부산 태풍 특보", r["reply"])
        self.assertTrue(any("부산 태풍 특보" in x["title"] for x in r["risks"]))
        self.assertTrue(any("실내/실외 구분" in c for c in r["caveats"]))

    def test_plan_prompt_carries_conditions_and_indoor_tags(self):
        self.llm_plan = self.plan_response()
        self.say("이번 주말 부산 갈래")
        self.say("상관없어요")
        prompt = self.llm_calls[-1][-1]["content"]
        self.assertIn("→ 실내 위주 (사유: 비/눈 예보)", prompt)
        self.assertIn("C3 | 문화시설 | 실내 | 부산박물관", prompt)
        self.assertIn("관련이슈: N1", prompt)

    # 3) 수정 대화
    def test_refine_reuses_data_and_keeps_context(self):
        self.llm_plan = self.plan_response()
        self.say("이번 주말 부산 갈래")
        self.say("상관없어요")
        self.assertEqual(self.raw_calls, 1)

        self.llm_plan = {"message": "2일차도 실내로 바꿨어요.", "follow_up": "", "days": [
            {"date": "2026-10-10", "theme": "", "items": [{"slot": "오전", "candidate_id": "C3", "note": ""}]},
            {"date": "2026-10-11", "theme": "실내", "items": [{"slot": "오전", "candidate_id": "C4", "note": ""}]}]}
        r = self.say("2일차는 실내로 바꿔줘")
        self.assertEqual(self.raw_calls, 1)  # 외부 API를 다시 부르지 않는다
        self.assertEqual(r["stage"], "planned")
        self.assertIn("영화의전당", r["reply"])
        self.assertEqual(r["slots"]["start_date"], "2026-10-10")  # 날짜가 바뀌지 않음
        prompt = self.llm_calls[-1][-1]["content"]
        self.assertIn("[모드] 수정", prompt)
        self.assertIn("[현재 일정]", prompt)
        self.assertIn("2일차는 실내로 바꿔줘", prompt)
        self.assertTrue(any(m["role"] == "assistant" for m in self.llm_calls[-1]))  # 이전 대화가 같이 전달됨

    def test_question_does_not_change_plan_or_dates(self):
        self.llm_plan = self.plan_response()
        self.say("이번 주말 부산 갈래")
        first = self.say("상관없어요")
        self.llm_plan = {"message": "내일은 비가 올 수 있어요.", "follow_up": "", "days": None}
        r = self.say("내일 비 와요?")  # '내일'이 있지만 변경 의도가 없으므로 출발일이 바뀌면 안 됨
        self.assertEqual(r["slots"]["start_date"], "2026-10-10")
        self.assertIn("비가 올 수 있어요", r["reply"])
        self.assertEqual(r["plan"], first["plan"])

    def test_changing_destination_regathers_and_replans(self):
        self.llm_plan = self.plan_response()
        self.say("이번 주말 부산 갈래")
        self.say("상관없어요")
        self.llm_plan = self.plan_response()
        r = self.say("제주로 바꿔줘")
        self.assertEqual(r["slots"]["region"], "제주")
        self.assertEqual(self.raw_calls, 2)
        self.assertIn("[모드] 새 일정", self.llm_calls[-1][-1]["content"])

    def test_food_request_does_not_regather_because_restaurants_are_always_collected(self):
        self.llm_plan = self.plan_response()
        self.say("이번 주말 부산 갈래")
        self.say("상관없어요")
        self.llm_plan = self.plan_response()
        self.say("맛집도 넣어줘")
        self.assertEqual(self.raw_calls, 1)  # 식사 장소용 음식점을 처음부터 받아둠
        self.assertIn("맛집", self.session.slots["preferences"])  # 식당 순위에 반영

    # 4) 입력 검증
    def test_past_date_and_too_long_are_rejected_politely(self):
        r = self.say("부산 3월 5일 2박 3일")  # 내년 3월로 해석되어 정상
        self.assertEqual(r["slots"]["start_date"], "2027-03-05")
        self.session.reset()
        r = self.say("부산 10월 10일부터 10월 30일까지")
        self.assertIn("최대 7일", r["reply"])
        self.assertEqual(r["slots"]["end_date"], "")

    def test_unsupported_region(self):
        self.llm_extract = {"region": "파리"}
        r = self.say("파리 가고 싶어요")
        self.assertIn("지원하지 않는", r["reply"])
        self.assertEqual(r["slots"]["region"], "")

    def test_llm_hallucinated_region_is_ignored(self):
        self.llm_extract = {"region": "제주", "start_date": "2026-11-01", "end_date": "2026-11-02"}
        r = self.say("안녕하세요")  # 지역/날짜를 말한 적이 없음
        self.assertEqual((r["slots"]["region"], r["slots"]["start_date"]), ("", ""))

    # 5) 장애 대응
    def test_works_without_llm(self):
        self.llm_fail = True
        r = self.say("이번 주말 부산 갈래요 커플이에요")
        self.assertEqual(r["slots"]["region"], "부산")
        self.assertEqual(r["slots"]["party"], "커플")  # 규칙으로 동행 인식
        self.assertEqual(r["stage"], "planned")          # LLM이 없어도 기본 일정을 만든다
        self.assertIn("1일차", r["reply"])
        self.assertTrue(any("규칙 기반 기본 일정" in c for c in r["caveats"]))
        # 비 오는 1일차(10/10)에는 실내 후보를 먼저 배치
        first_day_places = [it["place"]["name"] for it in r["plan"][0]["items"] if it["place"]]
        self.assertTrue(all(p in ("부산박물관", "영화의전당") for p in first_day_places[:2]))

    def test_refine_failure_keeps_previous_plan(self):
        self.llm_plan = self.plan_response()
        self.say("이번 주말 부산 갈래")
        first = self.say("상관없어요")
        self.llm_fail = True
        r = self.say("1일차 바꿔줘")
        self.assertIn("반영하지 못했어요", r["reply"])
        self.assertEqual(self.session.plan["days"][0]["items"][0]["candidate_id"], "C3")
        self.assertTrue(any("AI 연결 문제" in c for c in r["caveats"]))
        self.assertEqual(first["plan"][0]["date"], "2026-10-10")

    # 6) 속도: 짧은 메시지와 수정 요청에서는 AI 추출 호출을 생략
    EXTRACT_PREFIX = "너는 여행 플래너 챗봇의 '정보 추출기'"

    def _extract_calls(self):
        return [c for c in self.llm_calls if c[0]["content"].startswith(self.EXTRACT_PREFIX)]

    def test_short_messages_skip_extraction_llm(self):
        self.llm_plan = self.plan_response()
        with patch.object(self.chat, "CHAT_EXTRACT_LLM_MIN_CHARS", 40):
            self.say("부산 가려고요")
            self.say("이번 주말에요")
            r = self.say("커플이고 바다 보면서 조용히 걷고 싶어요")
        self.assertEqual(r["stage"], "planned")
        self.assertEqual(r["slots"]["party"], "커플")                # 규칙으로 인식
        self.assertIn("조용히", r["slots"]["preferences"])           # 나머지 말을 취향으로
        self.assertEqual(len(self._extract_calls()), 0)
        self.assertEqual(len(self.llm_calls), 1)                      # AI 호출은 일정 생성 한 번뿐
        self.assertIn("llm_sec", r["timings"])

    def test_slot_only_answers_do_not_pollute_preferences(self):
        with patch.object(self.chat, "CHAT_EXTRACT_LLM_MIN_CHARS", 40):
            self.say("부산 가려고요")
            r = self.say("내일부터 2박 3일이요")
        self.assertEqual(r["slots"]["preferences"], "")
        self.assertIn("누구와", r["reply"])  # 취향을 모르니 한 번 물어본다
        self.assertEqual(len(self.llm_calls), 0)

    def test_message_with_everything_keeps_preferences_without_llm(self):
        self.llm_plan = self.plan_response()
        with patch.object(self.chat, "CHAT_EXTRACT_LLM_MIN_CHARS", 40):
            r = self.say("이번 주말에 부산 갈래요 커플이고 조용한 바다 산책하고 싶어요")
        self.assertEqual(r["stage"], "planned")
        self.assertIn("조용한 바다", r["slots"]["preferences"])

    def test_refine_uses_only_one_llm_call(self):
        self.llm_plan = self.plan_response()
        with patch.object(self.chat, "CHAT_EXTRACT_LLM_MIN_CHARS", 40):
            self.say("이번 주말 부산 갈래")
            self.say("상관없어요")
            before = len(self.llm_calls)
            self.say("2일차는 실내로 바꿔줘")
        self.assertEqual(len(self.llm_calls) - before, 1)

    def test_long_message_still_uses_extraction_llm(self):
        long_msg = "이번 주말에 부산으로 여행을 가려고 하는데 커플이고 조용한 바다를 보면서 천천히 걷고 맛있는 것도 먹고 싶어요"
        self.assertGreaterEqual(len(long_msg), 40)
        self.llm_extract = {"party": "커플", "preferences": "조용한 바다, 산책"}
        self.llm_plan = self.plan_response()
        with patch.object(self.chat, "CHAT_EXTRACT_LLM_MIN_CHARS", 40):
            r = self.say(long_msg)
        self.assertEqual(len(self._extract_calls()), 1)
        self.assertIn("조용한 바다", r["slots"]["preferences"])

    # 7) 쓸 수 없는 AI 응답은 원인을 보여주고 기본 일정으로 대체
    def test_empty_ai_response_is_explained(self):
        self.llm_plan, self.llm_raw = None, ""
        self.say("이번 주말 부산 갈래")
        r = self.say("상관없어요")
        self.assertTrue(any("빈 응답" in c and "OLLAMA_THINK" in c for c in r["caveats"]), r["caveats"])
        self.assertIn("1일차", r["reply"])

    def test_unparseable_ai_response_shows_what_it_said(self):
        self.llm_plan, self.llm_raw = None, "죄송합니다, 일정을 만들 수 없어요"
        self.say("이번 주말 부산 갈래")
        r = self.say("상관없어요")
        self.assertTrue(any("JSON으로 읽지 못했어요" in c and "죄송합니다" in c for c in r["caveats"]), r["caveats"])

    # 8) 시간표: 시각·주소·이동·식사 / 시스템 문구 숨김
    COORD = {"1": ("35.1587", "129.1604"), "2": ("35.1532", "129.1186"), "3": ("35.1294", "129.0996"), "4": ("35.1710", "129.1270")}

    def _with_geo(self):
        self.extra_places = [
            dict(_place("20", "해운대 암소갈비", ctype="음식점", addr="부산 해운대구 중동 1"), content_type_id="39",
                 mapy="35.1600", mapx="129.1610", indoor=True),
            dict(_place("21", "광안리 횟집", ctype="음식점", addr="부산 수영구 광안동 2"), content_type_id="39",
                 mapy="35.1535", mapx="129.1190", indoor=True),
        ]
        for p in self.PLACES:
            p["mapy"], p["mapx"] = self.COORD[p["content_id"]]

    def test_reply_has_times_addresses_travel_and_real_restaurants(self):
        self._with_geo()
        self.llm_plan = self.plan_response()
        self.say("이번 주말 부산 갈래")
        r = self.say("상관없어요")
        reply = r["reply"]
        self.assertRegex(reply, r"\*\*10:00 - \d\d:\d\d\*\*")           # 10시에 시작하는 시간대
        self.assertIn("📍 위치: 부산 남구", reply)                              # 장소 주소 (부산박물관)
        self.assertIn("🚶", reply)
        self.assertRegex(reply, r"이동: .+ ➔ .+ \((도보|대중교통) 약 \d+분")      # 이동 수단과 예상 시간
        self.assertIn("🍽️ **점심 식사:", reply)
        self.assertIn("📍 위치: 부산 해운대구 중동 1", reply) if "암소갈비" in reply else self.assertIn("📍 위치: 부산 수영구 광안동 2", reply)
        day1 = [e for e in r["plan"][0]["events"] if e["kind"] == "meal"]
        self.assertTrue(day1 and day1[0]["place"]["name"] in ("해운대 암소갈비", "광안리 횟집"))  # 실제 음식점 데이터

    def test_same_restaurant_is_not_repeated_across_days(self):
        self._with_geo()
        self.llm_plan = self.plan_response()
        self.say("이번 주말 부산 갈래")
        r = self.say("상관없어요")
        meals = [e["place"]["name"] for d in r["plan"] for e in d["events"] if e["kind"] == "meal" and e["place"]]
        self.assertEqual(len(meals), len(set(meals)))

    def test_reply_hides_system_messages_and_candidate_ids(self):
        self._with_geo()
        self.llm_plan = dict(self.plan_response(), message="C1 중심으로 구성했어요 (C3)")
        self.say("이번 주말 부산 갈래")
        r = self.say("상관없어요")
        for bad in ("⚠️", "예보 범위", "ReadTimeout", "PublicDataAPIError", "조회 실패", "후보 장소가", "C1", "C3"):  # (뉴스 링크 주소는 테스트용 가짜 값이라 제외)
            self.assertNotIn(bad, r["reply"], bad)
        self.assertTrue(r["caveats"])  # 기술적인 내용은 caveats(개발자 정보)로만 전달

    def test_plan_reply_starts_with_title_no_intro_and_no_footnote(self):
        self._with_geo()
        self.llm_plan = dict(self.plan_response(), message="안녕하세요! 멋진 여행이 될 거예요.")
        self.say("이번 주말 부산 갈래")
        r = self.say("상관없어요")
        self.assertTrue(r["reply"].startswith("## 📅 부산 2일 여행 일정 ("), r["reply"][:60])  # 서론 없이 제목부터
        self.assertNotIn("안녕하세요", r["reply"])
        self.assertNotIn("※", r["reply"])

    def test_days_without_forecast_get_seasonal_text_not_error_text(self):
        self._with_geo()
        self.llm_plan = self.plan_response()
        self.say("10월 20일부터 2박 3일 부산")  # 예보 범위 밖
        r = self.say("상관없어요")
        self.assertIn("쾌청한 부산의 가을 날씨", r["reply"])
        self.assertNotIn("예보 범위", r["reply"])

    def test_reset_and_empty_message(self):
        self.say("이번 주말 부산 갈래")
        r = self.say("처음부터 다시 시작")
        self.assertEqual(r["slots"]["region"], "")
        self.assertIn("일정 짜줘", r["reply"])
        self.assertIn("맛집 알려줘", self.chat.handle_message(self.chat.ChatSession(), "", today=TODAY)["reply"])


if __name__ == "__main__":
    unittest.main()


# ── 요청 유형별 응답 (A: 여행지 추천 / C: 맛집·카페 / B: 일정) ──────────────────────
class IntentTests(unittest.TestCase):
    def test_detect_intent(self):
        import travel.chat as chat
        fresh = chat.ChatSession()
        d = lambda t, sess=fresh: chat.detect_intent(t, sess)
        self.assertEqual(d("성남 여행지만 추천해줘"), "recommend")
        self.assertEqual(d("가볼 만한 곳 알려줘"), "recommend")
        self.assertEqual(d("분당 맛집 알려줘"), "food")
        self.assertEqual(d("분당 카페"), "food")
        self.assertEqual(d("실내 데이트 장소 알려줘"), "recommend")
        self.assertEqual(d("성남 7일 일정 짜줘"), "plan")
        self.assertEqual(d("주말 데이트 코스 추천해줘"), "plan")       # '코스'가 있으면 일정
        self.assertEqual(d("맛집 위주로 일정 짜줘"), "plan")
        self.assertEqual(d("부산 가려고요"), "plan")                    # 일반 대화는 기존 흐름

    def test_preference_answer_is_not_mistaken_for_a_list_request(self):
        import travel.chat as chat
        s = chat.ChatSession()
        s.slots.update(region="부산", start_date="2026-10-10", end_date="2026-10-11")  # 동행·취향을 묻는 중
        self.assertEqual(chat.detect_intent("맛집 위주로 가고 싶어요", s), "plan")
        self.assertEqual(chat.detect_intent("근처 맛집 알려줘", s), "food")  # 명시적 요청이면 목록

    def test_in_plan_modification_stays_plan_but_explicit_ask_is_list(self):
        import travel.chat as chat
        s = chat.ChatSession()
        s.plan = {"days": []}
        self.assertEqual(chat.detect_intent("맛집도 넣어줘", s), "plan")
        self.assertEqual(chat.detect_intent("해운대 맛집 알려줘", s), "food")
        self.assertEqual(chat.detect_intent("내일 비 와요?", s), "plan")


class ListAnswerTests(unittest.TestCase):
    def setUp(self):
        import travel.chat as chat
        self.chat = chat
        self.calls = []

        def mk(i, title, ty, indoor, addr, ov=""):
            return {"source": "tourism", "content_id": str(i), "title": title, "addr": addr, "content_type_id": ty,
                    "content_type": {"12": "관광지", "14": "문화시설", "39": "음식점", "28": "레포츠"}[ty], "mapx": "127.12", "mapy": "37.38",
                    "image": "", "event_start": "", "event_end": "", "overview": ov, "indoor": indoor, "raw": {}}

        G = "경기도 성남시 분당구"
        self.places = [
            mk(1, "분당중앙공원", "12", False, f"{G} 성남대로 1", "호수와 산책로가 어우러진 도심 속 대표 공원이다. 사계절 걷기 좋다."),
            mk(2, "성남시립박물관", "14", True, f"{G} 성남대로 2", "성남의 역사와 문화를 전시하는 박물관이다."),
            mk(3, "탄천 산책로", "12", False, f"{G} 탄천로 3"),
            mk(4, "판교 아트센터", "14", True, f"{G} 판교로 4"),
            mk(10, "분당 한우마을", "39", True, f"{G} 서현로 10"),
            mk(11, "정자동 국수집", "39", True, f"{G} 정자로 11"),
            mk(12, "판교 칼국수", "39", True, f"{G} 판교로 12"),
            mk(13, "분당 스시", "39", True, f"{G} 서현로 13"),
            mk(14, "수내 갈비", "39", True, f"{G} 수내로 14"),
            mk(15, "정자 카페거리 커피", "39", True, f"{G} 정자로 15"),
            mk(16, "분당 로스터스 카페", "39", True, f"{G} 정자로 16"),
            mk(17, "서현 베이커리", "39", True, f"{G} 서현로 17"),
        ]

        def fill_intro(items, limit=8):
            for p in items:
                p["intro"] = {"firstmenu": "한우 갈비탕", "opentimefood": "11:00~21:00", "restdatefood": "매주 월요일",
                              "parkingfood": "가능"} if p["title"] == "분당 한우마을" else ({"treatmenu": "칼국수, 만두"} if "칼국수" in p["title"] else {})
            return []

        self.patches = [
            patch.object(chat, "_collect_candidates", side_effect=lambda *a, **k: (self.calls.append(a) or ([dict(p) for p in self.places], []))),
            patch.object(chat, "enrich", return_value=[]),
            patch.object(chat, "enrich_intro", side_effect=fill_intro),
            patch.object(chat, "chat_json_messages", side_effect=AssertionError("단발 추천은 AI 호출이 필요 없다")),
        ]
        for p in self.patches:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in self.patches])
        self.session = chat.ChatSession()

    def say(self, text):
        return self.chat.handle_message(self.session, text, today=TODAY, ranker=FakeRanker())

    # Type A
    def test_recommend_groups_by_theme_with_address_and_feature_and_no_dates_asked(self):
        r = self.say("성남 여행지만 추천해줘")
        reply = r["reply"]
        self.assertTrue(reply.startswith("## 성남 여행지 추천"))
        for cat in ("🌳 자연·공원", "🏛 문화·역사"):
            self.assertIn(cat, reply)
        self.assertIn("**분당중앙공원** (📍 경기도 성남시 분당구 성남대로 1)", reply)   # 장소명 + 주소
        self.assertIn("💡 호수와 산책로가 어우러진 도심 속 대표 공원이다.", reply)        # 소개글에서 가져온 특징
        self.assertNotIn("분당 한우마을", reply)                                          # 음식점은 여행지 목록에 없다
        self.assertNotIn("언제", reply)                                                   # 날짜를 묻지 않는다
        self.assertEqual(r["intent"], "recommend")
        self.assertTrue(r["places"] and r["places"][0]["category"])
        self.assertEqual(self.calls[0][0], "경기")                                        # 시도
        self.assertEqual(self.calls[0][-1], "성남")                                       # 세부 지역

    def test_indoor_request_filters_to_indoor_places(self):
        r = self.say("성남 실내 데이트 장소 알려줘")
        self.assertIn("성남시립박물관", r["reply"])
        self.assertNotIn("분당중앙공원", r["reply"])

    def test_feature_falls_back_gracefully_without_overview(self):
        r = self.say("성남 여행지 추천해줘")
        self.assertIn("탄천 산책로", r["reply"])
        self.assertRegex(r["reply"], r"탄천 산책로.*\n  - 💡 .+")          # 소개글이 없어도 빈 줄이 되지 않는다

    # Type C
    def test_food_gives_3_to_5_places_with_location_menu_and_access(self):
        r = self.say("분당 맛집 알려줘")
        reply = r["reply"]
        self.assertTrue(reply.startswith("## 분당 맛집 추천"))
        n = len(r["places"])
        self.assertTrue(3 <= n <= 5, n)
        self.assertEqual(reply.count("- 📍 위치:"), n)
        self.assertEqual(reply.count("- 🍴 대표 메뉴/특징:"), n)
        self.assertIn("🍴 대표 메뉴/특징: 한우 갈비탕", reply)
        self.assertIn("🚶 접근성: 주차 가능 · 영업 11:00~21:00 · 휴무 매주 월요일", reply)
        for cafe in ("카페", "베이커리"):
            self.assertNotIn(cafe, "".join(p["name"] for p in r["places"]))   # '맛집'에는 카페를 섞지 않는다
        self.assertEqual(self.calls[0][-1], "분당")

    def test_food_prefers_places_with_menu_and_access_info(self):
        r = self.say("분당 맛집 알려줘")
        names = [p["name"] for p in r["places"]]
        self.assertEqual(names[:2], ["분당 한우마을", "판교 칼국수"])   # 대표메뉴+영업정보가 있는 곳 → 취급메뉴만 있는 곳 순
        self.assertEqual(len(names), 5)
        self.assertTrue(r["places"][0]["access"])                        # 접근성 줄이 채워진 곳이 앞에 온다

    def test_cafe_request_returns_cafes_only(self):
        r = self.say("분당 카페 알려줘")
        names = [p["name"] for p in r["places"]]
        self.assertTrue(names and all(("카페" in n or "커피" in n or "베이커리" in n) for n in names), names)
        self.assertTrue(r["reply"].startswith("## 분당 카페 추천"))

    def test_menu_falls_back_to_treated_menu_then_type_phrase(self):
        r = self.say("분당 맛집 알려줘")
        by = {p["name"]: p for p in r["places"]}
        if "판교 칼국수" in by:
            self.assertIn("칼국수, 만두 (취급 메뉴)", r["reply"])
        self.assertNotIn("None", r["reply"])
        self.assertNotIn("⚠️", r["reply"])

    # 공통 규칙
    def test_asks_region_when_unknown_and_never_asks_dates(self):
        r = self.say("맛집 알려줘")
        self.assertIn("어느 지역", r["reply"])
        self.assertEqual(self.calls, [])

    def test_no_system_messages_or_greeting_in_list_answers(self):
        for q in ("성남 여행지만 추천해줘", "분당 맛집 알려줘"):
            reply = body(self.say(q)["reply"])
            for bad in ("⚠️", "ReadTimeout", "PublicDataAPIError", "예보", "안녕하세요", "제약"):
                self.assertNotIn(bad, reply, bad)

    def test_list_request_does_not_touch_an_existing_plan(self):
        import time
        self.session.plan = {"days": [{"theme": "", "items": []}]}
        self.session.slots.update(region="부산", area="", start_date="2026-10-10", end_date="2026-10-11")
        r = self.say("성남 맛집 알려줘")
        self.assertEqual(self.session.slots["region"], "부산")           # 일정의 지역·날짜는 그대로
        self.assertEqual(self.session.slots["start_date"], "2026-10-10")
        self.assertIsNotNone(self.session.plan)
        self.assertEqual(r["stage"], "planned")
        self.assertEqual(self.calls[0][-1], "성남")                      # 이번 질문의 지역으로 답한다

    def test_region_from_list_request_is_reused_for_a_later_plan(self):
        self.say("분당 맛집 알려줘")
        self.assertEqual((self.session.slots["region"], self.session.slots["area"]), ("경기", "분당"))


class SeasonTextTests(unittest.TestCase):
    def test_natural_text_for_each_season_with_place_name(self):
        from travel.conditions import season_hint
        self.assertIn("쾌청한 성남의 가을 날씨", season_hint("2026-10-20", "성남"))
        self.assertIn("화사한 성남의 봄 날씨", season_hint("2026-04-20", "성남"))
        self.assertIn("푸르른 성남의 여름 날씨", season_hint("2026-07-20", "성남"))
        self.assertIn("차분한 성남의 겨울 날씨", season_hint("2026-12-20", "성남"))
        self.assertNotIn("예보", season_hint("2026-10-20", "성남"))
        self.assertNotRegex(season_hint("2026-10-20", "성남"), r"\d+℃")   # 기온 수치를 지어내지 않는다


class ListHelpersTests(unittest.TestCase):
    def test_one_liner(self):
        from travel.lists import one_liner
        self.assertEqual(one_liner(""), "")
        self.assertEqual(one_liner("짧은 소개다."), "짧은 소개다.")
        long = "첫 문장은 이렇게 길게 이어지는 설명이다. " * 10
        out = one_liner(long, 60)
        self.assertLessEqual(len(out), 61)

    def test_categorize(self):
        from travel.lists import categorize
        c = lambda t, ty="12": categorize({"title": t, "content_type_id": ty})
        self.assertEqual(c("분당중앙공원"), "🌳 자연·공원")
        self.assertEqual(c("성남시립박물관", "14"), "🏛 문화·역사")
        self.assertEqual(c("탄천 산책로"), "🚶 힐링·산책")
        self.assertEqual(c("모란시장"), "🛍 쇼핑·실내")
        self.assertEqual(c("판교테크노밸리"), "🏙 도시·명소")        # '부산'처럼 흔한 지명 글자에 걸려 오분류되지 않는다
        self.assertEqual(c("브릭캠퍼스 부산", "14"), "🏛 문화·역사")


class IntroTests(unittest.TestCase):
    def test_menu_and_access_text(self):
        from collectors.tourism import access_text, menu_text
        intro = {"firstmenu": "한우 갈비탕", "treatmenu": "갈비탕, 수육", "opentimefood": "11:00~21:00", "parkingfood": "가능"}
        self.assertEqual(menu_text(intro), "한우 갈비탕")
        self.assertEqual(menu_text({"treatmenu": "칼국수"}), "칼국수")
        self.assertEqual(menu_text({}), "")
        self.assertEqual(access_text(intro), "주차 가능 · 영업 11:00~21:00")
        self.assertEqual(access_text({}), "")

    def test_get_intro_cleans_html_and_drops_empty_fields(self):
        import collectors.tourism as t
        payload = {"response": {"header": {"resultCode": "0000"}, "body": {"items": {"item": [
            {"contentid": "1", "firstmenu": "한우<br>갈비탕", "treatmenu": "", "opentimefood": "11:00&nbsp;~&nbsp;21:00"}]}}}}
        with patch.object(t, "call_public_api", return_value=payload) as m:
            out = t.get_intro("1", "39")
        self.assertEqual(m.call_args[0][1]["contentTypeId"], "39")
        self.assertEqual(out["firstmenu"], "한우 갈비탕")
        self.assertNotIn("treatmenu", out)

    def test_enrich_intro_stops_after_first_failure(self):
        import collectors.tourism as t
        places = [{"content_id": str(i), "content_type_id": "39"} for i in range(5)]
        with patch.object(t, "get_intro", side_effect=RuntimeError("quota")) as m:
            warns = t.enrich_intro(places)
        self.assertEqual(m.call_count, 1)  # 개발계정 일일 호출 한도를 아끼기 위해
        self.assertTrue(warns)
