"""
축제 추천 → 사용자가 고르면 추가: 일정에 마음대로 축제를 넣지 않고, 추천만 보여준 뒤 "1번 2일차에 추가해줘"에 넣는다.

    python -m unittest tests.test_festival_reco -v
"""
import unittest
from datetime import date
from unittest.mock import patch

from tests.test_offline import FakeRanker, _place

HOTEL = {"title": "아난티 코브", "category": "숙박>호텔", "addr": "부산광역시 기장군 기장해안로 268-31", "mapx": "129.2200000", "mapy": "35.1900000"}
TODAY = date(2026, 11, 9)
MSG = ("내가 다음달 12일에 2박3일로 부산 여행을 가는데 두번째 날에 일정이 좀 비어 그래서 괜찮은 축제 있나 한번 찾아주고, "
       "숙소는 '아난티 코브'라는 숙소로 이미 예약했으니 숙소는 찾아주지 않아도 돼.")


class FestivalRecoTests(unittest.TestCase):
    def setUp(self):
        import travel.chat as chat
        self.chat = chat
        sights = [_place(str(i), f"명소{i}", addr="부산광역시 기장군", mapx=str(129.22 + i * 0.001), mapy="35.19") for i in range(40)]
        eat = [dict(_place(f"r{i}", f"식당{i}", addr="부산광역시 기장군"), content_type_id="39", mapx=str(129.22 + i * 0.001), mapy="35.19") for i in range(8)]
        self.fests = [
            _place("f1", "기장불꽃축제", content_type_id="15", ctype="축제", addr="부산광역시 기장군", event_start="20261213", event_end="20261213",
                   mapx="129.230", mapy="35.195"),
            _place("f2", "해운대빛축제", content_type_id="15", ctype="축제", addr="부산광역시 해운대구", event_start="20261201", event_end="20261231",
                   mapx="129.160", mapy="35.160"),
            _place("f3", "첫날만축제", content_type_id="15", ctype="축제", addr="부산광역시 중구", event_start="20261212", event_end="20261212",
                   mapx="129.030", mapy="35.100"),
        ]

        def fake_gather(sido, area, start, end, include_food, today):
            return {"sido": sido, "area": area, "start": start.isoformat(), "end": end.isoformat(), "include_food": include_food,
                    "places": [dict(p, related_news_ids=[]) for p in sights + eat + self.fests], "news": [], "weather": [],
                    "weather_status": "out_of_range", "air": {"by_date": {}, "realtime": None, "warnings": []}, "warnings": [],
                    "fetched_at": __import__("time").time()}

        self.queries = []

        def fake_search(query, display=5):
            self.queries.append(query)
            return [HOTEL] if "아난티" in query else []

        for p in [patch.object(chat, "chat_json_messages", side_effect=RuntimeError("ollama down")),
                  patch.object(chat, "gather_raw", side_effect=fake_gather), patch.object(chat, "enrich", return_value=[]),
                  patch.object(chat, "search_local", side_effect=fake_search),
                  patch.object(chat, "_collect_festivals", side_effect=lambda sido, area, s, e: ([dict(f) for f in self.fests if f["event_start"] <= e.strftime("%Y%m%d") and f["event_end"] >= s.strftime("%Y%m%d")], []))]:
            p.start()
            self.addCleanup(p.stop)
        self.session = chat.ChatSession()

    def say(self, text):
        return self.chat.handle_message(self.session, text, today=TODAY, ranker=FakeRanker())

    def plan_first(self):
        r = self.say(MSG)
        if r["stage"] == "asking":  # 동행·취향 질문이 나오면 답한다
            r = self.say("상관없어요")
        return r

    @staticmethod
    def visits(r):
        return [[e["place"]["name"] for e in d["events"] if e["kind"] == "visit"] for d in r["plan"]]

    def test_the_example_message_gives_a_plan_with_the_hotel_and_festival_candidates(self):
        r = self.plan_first()
        self.assertIsNotNone(r["plan"], r["reply"][:300])
        self.assertIn("📅", r["reply"])
        # 숙소: 15시 체크인 · 마지막 날 11시 체크아웃
        d0, dl = r["plan"][0]["events"], r["plan"][-1]["events"]
        self.assertIn(("체크인", "15:00"), [(e["label"], e["start"]) for e in d0 if e["kind"] == "stay"])
        self.assertEqual(dl[0]["label"], "체크아웃 (11:00까지)")
        self.assertIn("여행 일정 상세 페이지", r["reply"])                      # 고치는 곳 안내
        self.assertNotIn("알려주세요", r["reply"].split("축제")[0])               # 체크인 시간을 되묻지 않는다
        # 축제는 추천만: 일정에는 없다
        self.assertEqual([n for v in self.visits(r) for n in v if "축제" in n], [])
        self.assertIn("축제·행사 추천", r["reply"])
        self.assertIn("기장불꽃축제", r["reply"])
        self.assertIn("해운대빛축제", r["reply"])
        self.assertIn("2일차(12/13)가 비어 있다고", r["reply"])                   # 둘째 날 안내
        self.assertLess(r["reply"].index("기장불꽃축제"), r["reply"].index("첫날만축제"))   # 둘째 날 열리는 축제가 먼저
        self.assertNotIn("축제 시간은 저희가 알 수 없어요", r["reply"])            # 고르기 전에는 시간을 묻지 않는다
        self.assertFalse(self.session.fest_pins)
        self.assertEqual(self.session.slots["preferences"], "")                  # 요청 문장이 취향으로 저장되지 않는다

    def test_user_picks_a_festival_and_it_is_added_on_that_day(self):
        self.plan_first()
        r = self.say("1번 2일차에 추가해줘")
        self.assertIn("기장불꽃축제", r["reply"].split("\n")[0])
        self.assertIn("2일차(12/13)에 추가했어요", r["reply"])
        day2 = self.visits(r)[1]
        self.assertIn("기장불꽃축제", day2)
        self.assertEqual(sum(v.count("기장불꽃축제") for v in self.visits(r)), 1)
        self.assertIn("축제 시간은 저희가 알 수 없어요", r["reply"])               # 고른 축제는 시간을 알려 달라고 안내
        self.assertEqual(r["stage"], "planned")
        # 숙소·체크인은 그대로
        self.assertIn(("체크인", "15:00"), [(e["label"], e["start"]) for e in r["plan"][0]["events"] if e["kind"] == "stay"])

    def test_liking_it_asks_first_then_yes_adds(self):
        self.plan_first()
        r = self.say("2번 괜찮네요")
        self.assertIn("넣을까요", r["reply"])
        self.assertNotIn("해운대빛축제", [n for v in self.visits(r) for n in v])   # 아직 안 넣음
        r = self.say("네")
        self.assertIn("추가했어요", r["reply"])
        self.assertIn("해운대빛축제", [n for v in self.visits(r) for n in v])

    def test_festival_name_works_and_the_default_day_is_the_asked_day(self):
        self.plan_first()
        r = self.say("기장불꽃축제 넣어줘")
        self.assertIn("2일차(12/13)에 추가했어요", r["reply"])

    def test_day_when_the_festival_is_not_open_is_refused(self):
        self.plan_first()
        r = self.say("1번 3일차에 추가해줘")
        self.assertIn("3일차에는 열리지 않아요", r["reply"])
        self.assertEqual([n for v in self.visits(r) for n in v if "축제" in n], [])

    def test_ambiguous_praise_asks_which(self):
        self.plan_first()
        r = self.say("좋아요 하나 추가해줘")
        self.assertIn("어느 축제", r["reply"])

    def test_unrelated_number_is_not_taken_as_a_festival(self):
        self.plan_first()
        self.say("1번 2일차에 추가해줘")
        r = self.say("3번 맛집 알려줘")
        self.assertNotIn("추가했어요", r["reply"])

    def test_asking_for_festivals_does_not_pin_them_but_focus_words_do(self):
        r = self.say("부산 다음달 12일 2박3일 일정 짜줘, 축제 위주로")
        self.assertIsNotNone(r["plan"])
        self.assertTrue(self.session.fest_pins)                                  # '위주로'는 예전처럼 축제를 일정의 중심으로

    def test_trip_and_lodging_in_one_breath_keeps_the_trip_part(self):
        r = self.say("부산 12월 12일 2박3일 여행 갈 건데 숙소는 '아난티 코브'야")        # 접속어 없이 이어 쓴 말
        self.assertEqual(self.session.slots["region"], "부산")
        self.assertEqual(self.session.slots["nights"], 2)
        self.assertIsNotNone(self.session.lodging)
        self.assertIn("아난티 코브", r["reply"])

    def test_greeting_request_does_not_become_the_thing_to_undo(self):
        self.plan_first()
        before = self.session.plan
        self.say("")                                                             # 인사말 요청
        self.assertEqual(self.chat.cancel_turn(self.session), "undone")          # 되돌리는 건 마지막 '말'(상관없어요)이다
        self.assertIsNone(self.session.plan)
        self.assertNotEqual(before, self.session.plan)

    def test_cancel_after_adding_restores_the_plan(self):
        self.plan_first()
        self.say("1번 2일차에 추가해줘")
        self.assertEqual(self.chat.cancel_turn(self.session), "undone")
        self.assertFalse(self.session.fest_pins)


if __name__ == "__main__":
    unittest.main()
