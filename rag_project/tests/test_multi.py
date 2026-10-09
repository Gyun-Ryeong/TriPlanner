"""다중 지역·새 요청 유형(숙박/축제/여행코스)·전국 시군구·고정 하단 서식 오프라인 테스트."""
import re
import time
import unittest
from datetime import date
from unittest.mock import patch

from tests.test_chat import body
from tests.test_offline import FakeRanker, _place

TODAY = date(2026, 10, 6)  # 화요일
FOOTER_LINES = [
    "- 본 서비스는 한국관광공사 TourAPI 4.0 국문 관광정보 API 및 공공데이터를 기반으로 동작합니다.",
    "- 날씨 및 미세먼지 예보는 기상청 단기예보 기준이며 세부 지역에 따라 다를 수 있습니다.",
    "- 실내/실외 구분은 장소 이름 및 카테고리 속성값으로 추정한 결과이므로 방문 전 재확인이 필요합니다.",
    "- 관광지, 식당, 숙박시설의 운영시간, 휴무일, 입장료는 방문 전 사전 확인을 권장합니다.",
]


def mk(i, title, ty, addr, **kw):
    d = dict(_place(str(i), title, addr=addr), content_type_id=ty,
             content_type={"12": "관광지", "14": "문화시설", "39": "음식점", "32": "숙박", "15": "축제공연행사", "25": "여행코스"}[ty],
             mapx="128.6", mapy="35.87", indoor=ty in ("14", "39", "32"))
    d.update(kw)
    return d


class ParseMultiTests(unittest.TestCase):
    def test_parse(self):
        from travel.chat import _last_region
        from travel.multi import parse_multi_trips as p
        r = p("대구 1박2일, 부산 2박3일 짜줘", _last_region)
        self.assertEqual([(t["sido"], t["nights"]) for t in r], [("대구", 1), ("부산", 2)])
        self.assertEqual([t["sido"] for t in p("1박2일 대구, 2박3일 부산", _last_region)], ["대구", "부산"])
        self.assertIsNone(p("부산 2박3일", _last_region))
        self.assertIsNone(p("성남 1박2일 성남 2박3일", _last_region))         # 같은 지역을 반복한 것은 다중 지역이 아니다
        self.assertEqual(p("제주 3일간 서울 당일치기", _last_region)[1]["nights"], 0)


class Base(unittest.TestCase):
    """지역마다 다른 장소를 돌려주는 가짜 수집기 + 가짜 AI."""

    def setUp(self):
        import travel.chat as chat
        self.chat = chat
        self.gathers, self.llm_prompts = [], []

        def fake_gather(sido, area, start, end, include_food, today):
            self.gathers.append((sido, area, start.isoformat(), end.isoformat()))
            places = [mk(100 + i, f"{sido}명소{i}", "14" if i % 3 == 0 else "12", f"{sido} 어딘가 {i}번지") for i in range(1, 9)]
            places += [mk(200 + i, f"{sido}맛집{i}", "39", f"{sido} 식당길 {i}") for i in range(1, 5)]
            return {"sido": sido, "area": area, "start": start.isoformat(), "end": end.isoformat(), "include_food": True,
                    "places": places, "news": [], "weather": [], "weather_status": "out_of_range",
                    "air": {"by_date": {}, "realtime": None, "warnings": []}, "warnings": [], "fetched_at": time.time(), "timings": {}}

        def fake_llm(messages, temperature=0.3):
            if messages[0]["content"].startswith("너는 여행 플래너 챗봇의 '정보 추출기'"):
                return {}, "{}"
            user = messages[-1]["content"]
            self.llm_prompts.append(user)
            ids = re.findall(r"^(C\d+) \|", user, re.M)
            a, b = re.search(r"기간: (\d{4}-\d{2}-\d{2}) ~ (\d{4}-\d{2}-\d{2})", user).groups()
            d0, d1 = date.fromisoformat(a), date.fromisoformat(b)
            days, k = [], 0
            for n in range((d1 - d0).days + 1):
                days.append({"date": date.fromordinal(d0.toordinal() + n).isoformat(), "theme": f"컨셉{n + 1}",
                             "items": [{"candidate_id": c, "note": "둘러보기"} for c in ids[k:k + 2]]})
                k += 2
            return {"message": "m", "days": days, "follow_up": ""}, "{}"

        self.patches = [patch.object(chat, "gather_raw", side_effect=fake_gather), patch.object(chat, "chat_json_messages", side_effect=fake_llm),
                        patch.object(chat, "enrich", return_value=[]), patch.object(chat, "lookup_regions", return_value=[]),
                        patch.object(chat, "CHAT_EXTRACT_LLM_MIN_CHARS", 40)]
        for p in self.patches:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in self.patches])
        self.session = chat.ChatSession()

    def say(self, text, session=None):
        return self.chat.handle_message(session or self.session, text, today=TODAY, ranker=FakeRanker())


class MultiTripTests(Base):
    def test_two_regions_ask_start_once_then_two_independent_plans(self):
        r = self.say("대구 1박2일, 부산 2박3일 짜줘")
        self.assertEqual(r["stage"], "asking")
        self.assertIn("대구 1박 2일, 부산 2박 3일", body(r["reply"]))
        self.assertIn("언제 출발", body(r["reply"]))
        self.assertEqual(self.gathers, [])

        r = self.say("10월 10일부터요")
        reply = body(r["reply"])
        self.assertEqual(r["stage"], "planned")
        self.assertIn("## 📅 대구 2일 여행 일정 (10/10(토) ~ 10/11(일))", reply)
        self.assertIn("## 📅 부산 3일 여행 일정 (10/12(월) ~ 10/14(수))", reply)   # 다음 지역은 다음 날부터
        daegu, busan = reply.split("\n\n---\n\n")
        self.assertIn("대구명소", daegu)
        self.assertNotIn("부산", daegu)                                              # 지역 데이터가 섞이지 않는다
        self.assertIn("부산명소", busan)
        self.assertNotIn("대구", busan)
        self.assertEqual([g[0] for g in self.gathers], ["대구", "부산"])
        self.assertEqual([t["region"] for t in r["trips"]], ["대구", "부산"])
        self.assertEqual(r["reply"].count("🛠 개발자 정보"), 1)

    def test_start_date_in_the_same_message_builds_immediately(self):
        r = self.say("10월 10일부터 대구 1박2일, 부산 2박3일 짜줘")
        self.assertEqual(r["stage"], "planned")
        self.assertEqual(len(r["trips"]), 2)

    def test_modification_goes_to_the_mentioned_region_only(self):
        self.say("10월 10일부터 대구 1박2일, 부산 2박3일 짜줘")
        n = len(self.gathers)
        r = self.say("부산 2일차는 실내로 바꿔줘")
        self.assertEqual(len(self.gathers), n)                      # 데이터를 다시 모으지 않는다
        self.assertIn("지역: 부산", self.llm_prompts[-1])
        self.assertIn("[모드] 수정", self.llm_prompts[-1])
        self.assertIn("부산 3일 여행 일정", body(r["reply"]))
        self.assertNotIn("대구", body(r["reply"]))
        self.assertEqual(r["reply"].count("🛠 개발자 정보"), 1)

    def test_modification_without_region_asks_which_one(self):
        self.say("10월 10일부터 대구 1박2일, 부산 2박3일 짜줘")
        r = self.say("2일차는 실내로 바꿔줘")
        self.assertIn("어느 지역 일정", body(r["reply"]))
        self.assertIn("대구 / 부산", body(r["reply"]))

    def test_new_region_discards_the_multi_trip_state(self):
        self.say("10월 10일부터 대구 1박2일, 부산 2박3일 짜줘")
        r = self.say("제주 2박3일 일정 짜줘")
        self.assertEqual(self.session.trips, {})
        self.assertEqual(r["slots"]["region"], "제주")
        self.assertNotIn("대구", body(r["reply"]))
        self.assertNotIn("부산", body(r["reply"]))
        self.assertIn("제주", body(r["reply"]))

    def test_past_date_and_too_long(self):
        self.say("대구 1박2일, 부산 2박3일 짜줘")
        r = self.say("2026년 10월 1일부터요")   # (연도 없는 지난 날짜는 내년으로 해석하므로 연도를 명시)
        self.assertIn("이미 지났어요", body(r["reply"]))
        self.assertEqual(self.gathers, [])
        s2 = self.chat.ChatSession()
        r = self.say("대구 9박10일, 부산 2박3일 짜줘", s2)
        r = self.say("10월 10일부터", s2)
        self.assertIn("최대 7일", body(r["reply"]))

    def test_pending_is_dropped_when_user_changes_to_another_request(self):
        self.say("대구 1박2일, 부산 2박3일 짜줘")
        r = self.say("제주 2박3일 일정 짜줘")           # 기다리던 요청 대신 새 지역 요청
        self.assertIsNone(self.session.pending_multi)
        self.assertEqual(r["slots"]["region"], "제주")


class RegionSwitchTests(Base):
    def test_new_region_in_a_plan_session_replaces_old_region_data(self):
        self.say("10월 10일부터 2박 3일 성남 일정 짜줘 상관없어요")
        r1 = self.say("상관없어요")
        self.assertEqual(r1["slots"]["region"], "경기")
        r = self.say("부산 2박3일 일정 짜줘")
        self.assertEqual((r["slots"]["region"], r["slots"]["area"]), ("부산", ""))   # 이전 세부 지역(성남)이 남지 않는다
        self.assertEqual(self.gathers[-1][0], "부산")
        self.assertIn("부산명소", body(r["reply"]))
        self.assertNotIn("경기명소", body(r["reply"]))

    def test_question_without_region_does_not_switch(self):
        self.say("10월 10일부터 2박 3일 부산 일정 짜줘")
        self.say("상관없어요")
        r = self.say("2일차는 실내로 바꿔줘")
        self.assertEqual(r["slots"]["region"], "부산")


class ListIntentsTests(unittest.TestCase):
    def setUp(self):
        import travel.chat as chat
        self.chat = chat
        self.calls = []
        by_region = lambda sido: [mk(1, f"{sido}한우집", "39", f"{sido} 식당길 1"), mk(2, f"{sido}국수집", "39", f"{sido} 식당길 2"),
                                  mk(3, f"{sido}공원", "12", f"{sido} 공원길 3"), mk(4, f"{sido}박물관", "14", f"{sido} 문화길 4")]
        stays = lambda sido: [mk(11, f"{sido}호텔", "32", f"{sido} 숙소길 1"), mk(12, f"{sido}펜션", "32", f"{sido} 숙소길 2")]

        def fake_intro(items, limit=8):
            for p in items:
                p["intro"] = {"checkintime": "15:00", "checkouttime": "11:00", "parkinglodging": "가능"} if p["content_type_id"] == "32" else \
                    {"taketime": "3시간", "distance": "5km"} if p["content_type_id"] == "25" else {}
            return []

        self.patches = [
            patch.object(chat, "_collect_candidates", side_effect=lambda sido, *a, **k: self.calls.append(("cand", sido, a[-1])) or (by_region(sido), [])),
            patch.object(chat, "_collect_type", side_effect=lambda sido, area, ct: self.calls.append((ct, sido, area)) or (
                stays(sido) if ct == "32" else [mk(21, f"{sido}도보코스", "25", f"{sido} 코스길", overview="걸으며 즐기는 코스다.")], [])),
            patch.object(chat, "_collect_festivals", side_effect=lambda sido, area, s, e: self.calls.append(("fest", sido, area)) or (
                [mk(31, f"{sido}가을축제", "15", f"{sido} 광장", event_start="20261010", event_end="20261012", overview="가을 축제다.")], [])),
            patch.object(chat, "enrich", return_value=[]), patch.object(chat, "enrich_intro", side_effect=fake_intro),
            patch.object(chat, "lookup_regions", return_value=[]),
            patch.object(chat, "chat_json_messages", side_effect=AssertionError("목록 요청은 AI 호출이 필요 없다")),
        ]
        for p in self.patches:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in self.patches])
        self.session = chat.ChatSession()

    def say(self, text):
        return self.chat.handle_message(self.session, text, today=TODAY, ranker=FakeRanker())

    def test_multiple_regions_get_independent_sections(self):
        r = self.say("대구, 부산 맛집 알려줘")
        reply = body(r["reply"])
        self.assertIn("## 대구 맛집 추천", reply)
        self.assertIn("## 부산 맛집 추천", reply)
        a, b = reply.split("\n\n---\n\n")
        self.assertNotIn("부산", a)
        self.assertNotIn("대구", b)
        self.assertEqual([c[1] for c in self.calls], ["대구", "부산"])

    def test_stay_list(self):
        r = self.say("성남 숙소 추천해줘")
        reply = body(r["reply"])
        self.assertEqual(r["intent"], "stay")
        self.assertTrue(reply.startswith("## 성남 숙박 추천"))
        self.assertIn("- 📍 위치: 경기 숙소길 1", reply)
        self.assertIn("체크인 15:00 · 체크아웃 11:00 · 주차 가능", reply)
        self.assertEqual(self.calls[0][0], "32")

    def test_festival_list(self):
        r = self.say("부산 축제 알려줘")
        reply = body(r["reply"])
        self.assertEqual(r["intent"], "festival")
        self.assertTrue(reply.startswith("## 부산 축제·행사"))
        self.assertIn("- 🗓 기간: 2026-10-10 ~ 2026-10-12", reply)
        self.assertEqual(self.chat.detect_intent("부산 축제 일정 알려줘", self.chat.ChatSession()), "festival")

    def test_recommended_course_list_vs_plan(self):
        r = self.say("성남 추천 여행코스 알려줘")
        self.assertEqual(r["intent"], "course")
        self.assertIn("## 성남 추천 여행코스", body(r["reply"]))
        self.assertIn("⏱ 소요 시간 3시간 · 거리 5km", body(r["reply"]))
        d = lambda t: self.chat.detect_intent(t, self.chat.ChatSession())
        self.assertEqual(d("주말 데이트 코스 추천해줘"), "plan")       # 일정을 짜달라는 '코스'
        self.assertEqual(d("성남 7일 코스 추천해줘"), "plan")

    def test_unknown_municipality_resolved_by_gazetteer(self):
        with patch.object(self.chat, "lookup_regions", return_value=[("전남", "곡성")]):
            r = self.say("곡성 맛집 알려줘")
        self.assertEqual(self.calls[0][1], "전남")
        self.assertIn("## 곡성 맛집 추천", body(r["reply"]))


class FooterTests(Base):
    def assert_footer(self, reply):
        self.assertEqual(reply.count("🛠 개발자 정보 (제약사항·한계)"), 1)
        tail = reply.split("\n\n---\n🛠 개발자 정보")[1]
        for line in FOOTER_LINES:
            self.assertIn(line, tail)
        self.assertTrue(reply.rstrip().endswith(FOOTER_LINES[-1]))          # 맨 끝에 온다

    def test_every_kind_of_answer_ends_with_the_footer(self):
        for text in ("안녕하세요", "부산 가려고요", "개발자 정보 보여줘"):
            self.assert_footer(self.say(text)["reply"])
        with patch("travel.news.search_news", return_value=[]):
            self.assert_footer(self.say("성남 요즘 소식 있어?")["reply"])
        self.assert_footer(self.say("10월 10일부터 2박 3일 부산 일정 짜줘")["reply"])
        self.assert_footer(self.say("상관없어요")["reply"])               # 일정 답변

    def test_greeting_has_no_footer_and_reset_does(self):
        self.assertNotIn("개발자 정보", self.chat.handle_message(self.chat.ChatSession(), "", today=TODAY)["reply"])
        self.assert_footer(self.say("처음부터 다시 시작")["reply"])

    def test_footer_is_static_even_when_apis_fail_and_dev_mode_is_off(self):
        with patch.object(self.chat, "DEV_MODE", False), patch("travel.news.search_news", side_effect=RuntimeError("ReadTimeout 401")):
            r = self.say("성남 요즘 소식 있어?")
        self.assert_footer(r["reply"])
        for leak in ("ReadTimeout", "RuntimeError", "401", "PublicDataAPIError"):
            self.assertNotIn(leak, r["reply"])                              # 실제 오류 내용은 하단 서식에도 들어가지 않는다
        self.assertEqual(r["caveats"], [])

    def test_footer_is_not_fed_back_into_the_ai_history(self):
        self.say("부산 가려고요")
        self.assertTrue(all("🛠 개발자 정보" not in m["content"] for m in self.session.history))


class TourismFieldTests(unittest.TestCase):
    def test_lodging_course_and_operating(self):
        from collectors.tourism import course_text, lodging_text, operating_text
        self.assertEqual(lodging_text({"checkintime": "15:00", "checkouttime": "11:00", "parkinglodging": "가능"}), "체크인 15:00 · 체크아웃 11:00 · 주차 가능")
        self.assertEqual(lodging_text({}), "")
        self.assertEqual(course_text({"taketime": "3시간", "distance": "5km"}), "소요 시간 3시간 · 거리 5km")
        self.assertEqual(operating_text({"checkintime": "14:00", "checkouttime": "12:00"}, "32"), "체크인 14:00 · 체크아웃 12:00")
        self.assertEqual(operating_text({"taketime": "2시간"}, "25"), "소요 시간 2시간")

    def test_lodging_and_courses_never_enter_the_itinerary_candidates(self):
        from travel.places import SIGHT_TYPES
        self.assertTrue({"32", "25", "39"}.isdisjoint(SIGHT_TYPES))


class GazetteerTests(unittest.TestCase):
    def setUp(self):
        import travel.gazetteer as gz
        self.gz = gz
        gz.reset_for_tests()
        self.addCleanup(gz.reset_for_tests)
        self.calls = 0
        SIG = {"전남": {"곡성군": "1", "담양군": "2"}, "강원": {"영월군": "1", "고성군": "2", "춘천시": "3"}, "경남": {"고성군": "5", "창원시 성산구": "6"},
               "경기": {"성남시 분당구": "135", "고양시 덕양구": "10"}}

        def fake_sig(code):
            self.calls += 1
            return SIG.get(code, {})

        self.patches = [patch("travel.ldong.resolve_ldong", side_effect=lambda s: (s, False)),
                        patch("collectors.tourism.fetch_ldong_sigungu", side_effect=fake_sig),
                        patch.object(gz.config, "GAZETTEER_CACHE_PATH", __import__("tempfile").mkdtemp() + "/gz.json")]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)

    def test_lookup(self):
        gz = self.gz
        self.assertEqual(gz.lookup_regions("곡성 맛집 알려줘"), [("전남", "곡성")])
        self.assertEqual(gz.lookup_regions("영월이랑 담양 여행"), [("강원", "영월"), ("전남", "담양")])
        self.assertEqual(gz.lookup_regions("분당 한우마을"), [("경기", "분당")])

    def test_ambiguous_and_unrelated_words_are_ignored(self):
        gz = self.gz
        self.assertEqual(gz.lookup_regions("고성 어때"), [])                 # 강원/경남에 모두 있어 모호
        self.assertEqual(gz.lookup_regions("오늘 날씨 어때"), [])
        self.assertEqual(gz.lookup_regions("고양이랑 갈래"), [])               # '고양이'를 고양시로 읽지 않는다
        self.assertEqual(gz.lookup_regions("화성 탐사 이야기"), [])
        self.assertEqual(gz.lookup_regions("고양시 맛집"), [("경기", "고양")])  # 시를 붙이면 인식

    def test_index_is_built_once(self):
        gz = self.gz
        gz.lookup_regions("곡성")
        n = self.calls
        gz.lookup_regions("담양")
        self.assertEqual(self.calls, n)

    def test_failure_is_not_retried_immediately(self):
        gz = self.gz
        with patch("collectors.tourism.fetch_ldong_sigungu", side_effect=RuntimeError("api down")) as m:
            self.assertEqual(gz.lookup_regions("곡성"), [])
            n = m.call_count
            self.assertEqual(gz.lookup_regions("곡성"), [])
            self.assertEqual(m.call_count, n)                                  # 쿨다운 동안은 API를 다시 두드리지 않는다


if __name__ == "__main__":
    unittest.main()
