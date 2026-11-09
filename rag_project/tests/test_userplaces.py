"""
사용자가 말한 숙소·장소·시간 오프라인 테스트: 말 읽기 → 위치 찾기(네이버 지역검색은 가짜) → 일정 반영(시간 고정·숙소 출발/복귀).

    python -m unittest tests.test_userplaces -v
"""
import unittest
from datetime import date
from unittest.mock import patch

from tests.test_offline import FakeRanker, _place


class ParseTests(unittest.TestCase):
    def p(self, text):
        from travel.userplaces import parse_directives
        return parse_directives(text)

    def test_reads_stay_visits_times_and_days(self):
        r = self.p("숙소는 판교 스타호텔이야, 2일차 12시에 단풍 카페 들를게, 저녁 7시에 하늘식당 예약했어")
        kinds = [(i["kind"], i["name"], i["time"], i["day"]) for i in r["items"]]
        self.assertEqual(kinds, [("stay", "스타호텔", None, None), ("visit", "단풍", (720, None), 2), ("visit", "하늘식당", (1140, None), None)])
        self.assertTrue(r["only"])

    def test_numbered_list_and_minutes(self):
        r = self.p("1. 단풍 카페 오후 3시\n2. 하품스베이크 판교점 오전 11시 30분")
        self.assertEqual([i["time"] for i in r["items"]], [(900, None), (690, None)])
        self.assertEqual(r["items"][1]["name"], "하품스베이크 판교점")

    def test_ordinary_requests_are_not_places(self):
        for t in ("내일 부산 가려고 해요", "성남 2박 3일 일정 짜줘", "맛집도 넣어줘", "2일차 11시에 출발할게", "저녁 7시부터 9시",
                  "토요일 오전 9시 출발, 부산 1박2일", "맛집 위주로 가고 싶어요", "광안리 횟집 가고 싶어"):
            self.assertEqual(self.p(t)["items"], [], t)

    def test_drop_request(self):
        r = self.p("단풍 카페 빼줘")
        self.assertEqual([(i["kind"], i["name"]) for i in r["items"]], [("drop", "단풍")])

    def test_mixed_message_keeps_the_rest_for_the_normal_flow(self):
        r = self.p("단풍 카페 오후 3시에 들를게, 2일차는 실내로 바꿔줘")
        self.assertEqual(len(r["items"]), 1)
        self.assertFalse(r["only"])
        self.assertIn("실내", r["rest"])


class TimelineWithBaseTests(unittest.TestCase):
    HOTEL = {"content_id": "h", "title": "스타호텔", "mapy": "35.100", "mapx": "127.100", "content_type_id": "32", "content_type": "숙소", "addr": ""}

    @staticmethod
    def P(i, title, lon, ty="12", **kw):
        return dict({"content_id": str(i), "title": title, "mapy": "35.101", "mapx": str(lon), "content_type_id": ty,
                     "content_type": "관광지", "addr": "", "indoor": False}, **kw)

    def test_day_starts_at_and_returns_to_the_lodging_nearest_first(self):
        from travel.schedule import build_timeline
        near, mid, far = self.P(1, "가까운곳", 127.101), self.P(2, "중간", 127.110), self.P(3, "먼곳", 127.130)
        ev = build_timeline([{"place": x, "note": ""} for x in (far, near, mid)], [], set(), self.HOTEL)
        self.assertEqual((ev[0]["kind"], ev[0]["from"]["title"], ev[0]["to"]["title"]), ("move", "스타호텔", "가까운곳"))
        visits = [e["place"]["title"] for e in ev if e["kind"] == "visit"]
        self.assertEqual(visits, ["가까운곳", "중간", "먼곳"])             # 숙소에서 가까운 곳부터
        self.assertEqual((ev[-1]["kind"], ev[-1]["to"]["title"]), ("move", "스타호텔"))   # 마지막은 숙소 복귀

    def test_fixed_place_first_of_day_gets_a_departure_in_time(self):
        from travel.schedule import build_timeline
        cafe = self.P(9, "단풍", 127.120, stay_min=60)
        ev = build_timeline([{"place": cafe, "note": "", "fixed": (9 * 60, 10 * 60)}], [], set(), self.HOTEL)
        self.assertEqual(ev[0]["kind"], "move")
        self.assertLessEqual(ev[0]["end"], "09:00")
        fixed = next(e for e in ev if e["kind"] == "visit")
        self.assertEqual((fixed["start"], fixed["end"]), ("09:00", "10:00"))

    def test_a_restaurant_the_user_picked_counts_as_that_meal(self):
        from travel.schedule import build_timeline
        spot = self.P(1, "명소", 127.101)
        rest = self.P(7, "하늘식당", 127.102, "39", meal=True, stay_min=70)
        other = [self.P(10, "다른식당", 127.103, "39")]
        ev = build_timeline([{"place": spot, "note": ""}, {"place": rest, "note": "", "fixed": (12 * 60, 13 * 60 + 10)}], other, set())
        self.assertFalse([e for e in ev if e["kind"] == "meal" and e["label"] == "점심"])
        self.assertTrue([e for e in ev if e["kind"] == "meal" and e["label"] == "저녁"])


HOTEL = {"title": "스타호텔 판교점", "category": "숙박>호텔", "addr": "전북 전주시 덕진구 호텔로 1", "mapx": "127.1000000", "mapy": "35.1000000"}
CAFE = {"title": "단풍", "category": "카페,디저트>카페", "addr": "전북 전주시 덕진구 단풍로 3", "mapx": "127.1030000", "mapy": "35.1010000"}
DINER = {"title": "하늘식당", "category": "음식점>한식", "addr": "전북 전주시 덕진구 하늘로 5", "mapx": "127.1050000", "mapy": "35.1010000"}


class FlowBase(unittest.TestCase):
    DB = None  # {검색어 조각: 검색 결과 목록}. None 이면 아래 기본값
    def setUp(self):
        import travel.chat as chat
        self.chat = chat
        sights = [_place(str(i), f"명소{i}", addr="전북 전주시 덕진구", mapx=str(127.1 + i * 0.001), mapy="35.101") for i in range(40)]
        sights.append(_place("far", "아주먼곳", addr="전북 군산시", mapx="126.0", mapy="36.0"))
        eat = [dict(_place(f"r{i}", f"식당{i}", addr="전북 전주시"), content_type_id="39", mapx=str(127.1 + i * 0.001), mapy="35.101") for i in range(8)]

        def fake_gather(sido, area, start, end, include_food, today):
            return {"sido": sido, "area": area, "start": start.isoformat(), "end": end.isoformat(), "include_food": include_food,
                    "places": [dict(p, related_news_ids=[]) for p in sights + eat], "news": [], "weather": [], "weather_status": "out_of_range",
                    "air": {"by_date": {}, "realtime": None, "warnings": []}, "warnings": [], "fetched_at": __import__("time").time()}

        self.queries = []
        self.db = dict(self.DB) if self.DB is not None else {"스타호텔": [HOTEL], "단풍": [CAFE], "하늘식당": [DINER]}  # 테스트마다 따로
        db = self.db

        def fake_search(query, display=5):
            self.queries.append(query)
            for k, v in db.items():
                if k in query:
                    return v
            return []

        for p in [patch.object(chat, "chat_json_messages", side_effect=RuntimeError("ollama down")),
                  patch.object(chat, "gather_raw", side_effect=fake_gather), patch.object(chat, "enrich", return_value=[]),
                  patch.object(chat, "search_local", side_effect=fake_search)]:
            p.start()
            self.addCleanup(p.stop)
        self.session = chat.ChatSession()

    def say(self, text):
        return self.chat.handle_message(self.session, text, today=date(2026, 10, 21), ranker=FakeRanker())

    def make_plan(self):
        return self.say("전주 다음주 주말에 2박 3일 혼자 여행 일정 짜줘")

    @staticmethod
    def find(r, name):
        for di, d in enumerate(r["plan"]):
            for e in d["events"]:
                if e["kind"] == "visit" and e["place"]["name"] == name:
                    return di, e
        return None, None

    def assert_days_clean(self, r):
        for d in r["plan"]:
            ev = d["events"]
            for a, b in zip(ev, ev[1:]):
                self.assertLessEqual(a["end"], b["start"], (a, b))

class ChatFlowTests(FlowBase):
    def test_places_after_a_plan_exists_are_applied_without_ai(self):
        self.make_plan()
        r = self.say("숙소는 판교 스타호텔이야, 2일차 12시에 단풍 카페 들를게, 저녁 7시에 하늘식당 예약했어")
        self.assertIn("이렇게 이해했어요", r["reply"])
        self.assertIn("스타호텔 판교점", r["reply"])
        di, cafe = self.find(r, "단풍")
        self.assertEqual((di, cafe["start"], cafe["end"], cafe["fixed"]), (1, "12:00", "13:00", True))       # 2일차 12시, 카페 60분
        dj, diner = self.find(r, "하늘식당")
        self.assertEqual((diner["start"], diner["end"], diner["fixed"]), ("19:00", "20:10", True))
        self.assert_days_clean(r)
        for d in r["plan"]:                                                                                   # 매일 숙소에서 출발·복귀
            self.assertEqual(d["events"][0]["from"], "스타호텔 판교점")
            self.assertEqual(d["events"][-1]["to"], "스타호텔 판교점")
        # 7시에 고른 식당은 저녁을 대신하지만, 12시에 고른 카페는 점심을 대신하지 않는다
        self.assertFalse([e for e in r["plan"][dj]["events"] if e["kind"] == "meal" and e["label"] == "저녁"])
        self.assertTrue([e for e in r["plan"][di]["events"] if e["kind"] == "meal" and e["label"] == "점심"])

    def test_places_given_together_with_the_plan_request(self):
        r = self.say("전주 다음주 주말에 2박 3일 혼자 여행 일정 짜줘, 2일차 오후 3시에 단풍 카페 들를게")
        self.assertTrue(r["reply"].startswith("📌 **이렇게 이해했어요**"))
        di, e = self.find(r, "단풍")
        self.assertEqual((di, e["start"], e["fixed"]), (1, "15:00", True))
        self.assert_days_clean(r)

    def test_other_stops_of_that_day_are_gathered_around_the_fixed_place(self):
        self.make_plan()
        r = self.say("2일차 오후 3시에 단풍 카페 들를게")
        names = [e["place"]["name"] for e in r["plan"][1]["events"] if e["kind"] == "visit"]
        self.assertIn("단풍", names)
        self.assertNotIn("아주먼곳", names)
        self.assertGreaterEqual(len(names), 3)

    def test_time_can_be_changed_and_a_place_can_be_removed(self):
        self.make_plan()
        self.say("2일차 12시에 단풍 카페 들를게")
        r = self.say("단풍 카페 오후 4시로 바꿔줘")
        self.assertEqual(self.find(r, "단풍")[1]["start"], "16:00")
        self.assertEqual(self.find(r, "단풍")[0], 1)                       # 날짜는 처음 말한 2일차 그대로
        r = self.say("단풍 카페 빼줘")
        self.assertEqual(self.find(r, "단풍"), (None, None))
        self.assertIn("뺐어요", r["reply"])

    def test_move_to_another_day_keeps_the_time(self):
        self.make_plan()
        self.say("2일차 12시에 단풍 카페 들를게")
        r = self.say("단풍 카페 3일차로 옮겨줘")
        di, e = self.find(r, "단풍")
        self.assertEqual((di, e["start"]), (2, "12:00"))
        self.assertEqual(self.queries[1:], [])                              # 옮기기는 새 장소 검색을 하지 않는다
        self.assert_days_clean(r)

    def test_same_name_in_another_region_is_not_chosen(self):
        import travel.chat as chat
        self.make_plan()
        with patch.object(chat, "search_local", side_effect=lambda q, display=5: [dict(CAFE, addr="서울특별시 용산구 단풍로 3")]):
            r = self.say("2일차 12시에 단풍 카페 들를게")
        self.assertIn("위치를 찾지 못했어요", r["reply"])                   # 전북 여행인데 서울 가게는 고르지 않는다
        self.assertEqual(self.find(r, "단풍"), (None, None))

    def test_unknown_place_is_reported_not_invented(self):
        self.make_plan()
        r = self.say("2일차 12시에 없는맛집 들를게")
        self.assertIn("위치를 찾지 못했어요", r["reply"])
        self.assertEqual(self.find(r, "없는맛집"), (None, None))

    def test_ordinary_messages_never_call_the_place_search(self):
        for t in ("전주 다음주 주말에 2박 3일 혼자 여행 일정 짜줘", "2일차는 실내로 바꿔줘"):
            self.say(t)
        self.assertEqual(self.queries, [])

    def test_place_already_in_tourapi_is_reused_without_searching(self):
        self.make_plan()
        r = self.say("2일차 오후 2시에 명소7 들를게")
        self.assertEqual(self.queries, [])
        self.assertEqual(self.find(r, "명소7")[1]["start"], "14:00")

    def test_changing_region_drops_places_from_the_old_trip(self):
        self.make_plan()
        self.say("2일차 12시에 단풍 카페 들를게")
        self.session.slots.update(region="부산", area="")                  # 다른 지역으로 바뀐 상태
        days = [{"theme": "", "items": []}]
        self.chat._apply_user_places(self.session, days, {}, lambda p: "C1", [{"outdoor_ok": None}], [])
        self.assertEqual(days[0]["items"], [])


GN_HOTEL = {"title": "신라모노그램 강릉 레지던스", "category": "숙박>호텔", "addr": "강원특별자치도 강릉시 해안로 210",
            "mapx": "127.1000000", "mapy": "35.1010000"}
USER_MSG = ("다음 주 목요일쯤으로 3박4일 강릉 여행을 갈 예정이야. 근데 숙소는 이미 예약해놨어 "
            "'신라모노그램 강릉'숙소를 기반으로 효율적인 동선을 짜줬으면 좋겠어.")


class LodgingParseTests(unittest.TestCase):
    def test_hotel_name_in_quotes_is_read_even_with_the_trip_info_in_the_same_message(self):
        from travel.userplaces import parse_directives
        r = parse_directives(USER_MSG)
        stay = [i for i in r["items"] if i["kind"] == "stay"]
        self.assertEqual(len(stay), 1)
        self.assertEqual((stay[0]["name"], stay[0]["region_tokens"], stay[0]["display"]), ("신라모노그램", ["강릉"], "신라모노그램 강릉"))
        self.assertEqual(len(r["items"]), 1)                                 # 여행 정보 문장이 장소로 읽히지 않는다

    def test_stay_and_visit_in_one_sentence_and_names_ending_in_particle_letters(self):
        from travel.userplaces import parse_directives
        r = parse_directives("숙소는 경포 스카이베이 호텔이고 첫날 오후 2시에 안목해변 카페거리 들를게")
        self.assertEqual([i["kind"] for i in r["items"]], ["stay", "visit"])
        self.assertIn("스카이베이", r["items"][0]["search_tokens"])           # 검색어에서는 '스카이베이'를 '스카이베'로 자르지 않는다
        self.assertEqual(r["items"][1]["time"], (840, None))

    def test_filler_words_do_not_end_up_in_the_name(self):
        from travel.userplaces import parse_directives
        r = parse_directives("강릉 3박4일 갈 건데 숙소는 신라모노그램 강릉이야")
        self.assertEqual(r["items"][0]["tokens"], ["신라모노그램"])


class LodgingHoldTests(FlowBase):
    """숙소를 못 찾았을 때: 마음대로 다른 일정을 짜지 않고 되묻는다."""
    DB = {}                                           # 어떤 검색에도 결과가 없다

    def test_unfound_lodging_pauses_planning_and_asks(self):
        r = self.say(USER_MSG)
        self.assertIn("위치를 찾지 못했어요", r["reply"])
        self.assertIn("신라모노그램 강릉", r["reply"])
        self.assertIn("기다릴게요", r["reply"])
        self.assertEqual(r["stage"], "asking")
        self.assertIsNone(r["plan"])                  # 일정을 만들지 않는다
        self.assertEqual(self.session.lodging_hold, "신라모노그램 강릉")
        self.assertEqual((self.session.slots["region"], self.session.slots["area"]), ("강원", "강릉"))   # 여행 정보는 이미 읽어 둠
        self.assertNotIn("숙소", self.session.slots["preferences"])                              # 숙소 문장이 취향으로 저장되지 않는다

    def test_answering_with_the_name_resolves_it_and_then_plans_around_it(self):
        r = self.say(USER_MSG)
        self.db["신라모노그램"] = [GN_HOTEL]            # 이번엔 검색에 잡히는 이름으로 다시 알려줌
        r = self.say("신라모노그램 강릉")
        self.assertIn("신라모노그램 강릉 레지던스", r["reply"])
        self.assertEqual(self.session.lodging_hold, "")
        self.assertIn("누구와", r["reply"])                # 숙소가 정해졌으니 이제 동행·취향을 한 번 묻는다 (보통 흐름)
        r = self.say("상관없어요")
        self.assertIsNotNone(r["plan"])
        self.assertEqual(r["plan"][0]["events"][0]["from"], "신라모노그램 강릉 레지던스")

    def test_no_lodging_option_plans_without_it(self):
        self.say(USER_MSG)
        r = self.say("숙소 없이 진행해줘")
        self.assertEqual(self.session.lodging_hold, "")
        self.assertNotIn("숙소", self.session.slots["preferences"])           # "숙소 없이 진행"이 취향으로 저장되지 않는다
        r = self.say("상관없어요")
        self.assertIsNotNone(r["plan"])
        self.assertIsNone(self.session.lodging)
        self.assertNotEqual(r["plan"][0]["events"][0]["kind"], "move")          # 숙소가 없으니 숙소에서 출발하는 이동이 없다

    def test_when_a_plan_already_exists_a_missing_lodging_does_not_block(self):
        self.db["신라모노그램"] = [GN_HOTEL]
        self.say("강릉 3박4일 다음주 목요일 일정 짜줘")
        self.say("상관없어요")                        # 동행·취향 질문에 답하면 일정이 나온다
        self.db.clear()
        r = self.say("숙소는 '없는호텔 강릉'이야")
        self.assertIsNotNone(r["plan"])
        self.assertIn("아직 반영하지 못했어요", r["reply"])
        self.assertEqual(self.session.lodging_hold, "")


class LodgingFoundTests(FlowBase):
    DB = {"신라모노그램": [GN_HOTEL]}

    def test_the_users_original_message_now_plans_around_the_hotel(self):
        r = self.say(USER_MSG)
        self.assertTrue(r["reply"].startswith("📌 **이렇게 이해했어요**"))
        self.assertIn("신라모노그램 강릉 레지던스", r["reply"])
        self.assertNotIn("위치를 찾지 못했어요", r["reply"])
        self.assertEqual(self.session.slots["preferences"], "")               # 숙소·여행 문장이 취향으로 저장되지 않는다
        r = self.say("상관없어요")                                              # 동행·취향 질문(한 번)에 답하면 일정이 나온다
        self.assertIsNotNone(r["plan"])
        for d in r["plan"]:
            self.assertEqual(d["events"][0]["from"], "신라모노그램 강릉 레지던스")
            self.assertEqual(d["events"][-1]["to"], "신라모노그램 강릉 레지던스")


if __name__ == "__main__":
    unittest.main()
