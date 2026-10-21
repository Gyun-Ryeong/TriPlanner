"""
축제 질문이 일정 생성으로 빠지지 않는지, 말한 날짜(또는 여행 날짜)에 열리는 축제를 찾는지 확인하는 오프라인 테스트.

    python -m unittest tests.test_festival_intent -v
"""
import unittest
from datetime import date
from unittest.mock import patch

from tests.test_offline import FakeRanker

TODAY = date(2026, 10, 6)  # 화요일


class FestivalIntentTests(unittest.TestCase):
    def setUp(self):
        import travel.chat as chat
        self.chat = chat

    def d(self, text, session=None):
        return self.chat.detect_intent(text, session or self.chat.ChatSession())

    def test_festival_question_with_duration_is_a_list(self):
        self.assertEqual(self.d("부산 2박3일 축제 추천해줘"), "festival")
        self.assertEqual(self.d("10월 10일부터 2박3일 부산 축제 알려줘"), "festival")
        self.assertEqual(self.d("11월 부산 축제"), "festival")
        self.assertEqual(self.d("부산 축제 일정 알려줘"), "festival")

    def test_asking_to_plan_around_festivals_is_still_a_plan(self):
        self.assertEqual(self.d("부산 1박2일 축제 위주로 일정 짜줘"), "plan")
        self.assertEqual(self.d("부산 공연 보러 가는 코스 짜줘"), "plan")

    def test_preference_answer_and_plan_modification_are_not_lists(self):
        s = self.chat.ChatSession()
        s.slots.update(region="부산", start_date="2026-10-10", end_date="2026-10-12")  # 동행·취향을 묻는 중
        self.assertEqual(self.d("축제 같은 거 좋아요", s), "plan")
        self.assertEqual(self.d("애들 있어서 맛집 위주로", s), "plan")
        s.plan = {"days": []}
        self.assertEqual(self.d("이 기간에 하는 축제 있어", s), "festival")
        self.assertEqual(self.d("축제도 넣어줘", s), "plan")


class FestivalRangeTests(unittest.TestCase):
    def setUp(self):
        import travel.chat as chat
        self.chat = chat
        self.ranges = []

        def fake_fest(sido, area, start, end):
            self.ranges.append((start, end))
            return [{"source": "tourism", "content_id": "f1", "title": "부산불꽃축제", "addr": "부산 수영구", "content_type_id": "15",
                     "content_type": "축제", "mapx": "129.1", "mapy": "35.1", "image": "", "event_start": "20261010",
                     "event_end": "20261011", "overview": "", "indoor": False, "raw": {}}], []

        for p in [patch.object(chat, "_collect_festivals", side_effect=fake_fest), patch.object(chat, "enrich", return_value=[]),
                  patch.object(chat, "gather_raw", side_effect=AssertionError("일정을 만들면 안 됨"))]:
            p.start()
            self.addCleanup(p.stop)

    def say(self, session, text):
        return self.chat.handle_message(session, text, today=TODAY, ranker=FakeRanker())

    def test_dates_in_question_set_the_search_range(self):
        r = self.say(self.chat.ChatSession(), "10월 10일부터 2박3일 부산 축제 알려줘")
        self.assertEqual(self.ranges[-1], (date(2026, 10, 10), date(2026, 10, 12)))
        self.assertEqual(r["intent"], "festival")
        self.assertIn("부산불꽃축제", r["reply"])
        self.assertIn("10/10(토) ~ 10/12(월)", r["reply"])

    def test_month_only(self):
        self.say(self.chat.ChatSession(), "11월 부산 축제")
        self.assertEqual(self.ranges[-1], (date(2026, 11, 1), date(2026, 11, 30)))

    def test_this_period_uses_the_trip_dates(self):
        s = self.chat.ChatSession()
        s.slots.update(region="부산", start_date="2026-10-20", end_date="2026-10-22")
        s.plan = {"days": []}
        self.say(s, "이 기간에 하는 축제 있어")
        self.assertEqual(self.ranges[-1], (date(2026, 10, 20), date(2026, 10, 22)))

    def test_no_date_means_next_60_days(self):
        self.say(self.chat.ChatSession(), "부산 축제 알려줘")
        self.assertEqual(self.ranges[-1], (TODAY, date(2026, 12, 5)))



class FestivalPlanTests(unittest.TestCase):
    """축제 목록을 본 뒤 '저거 기준으로 다시 짜줘' → 축제를 열리는 날짜에 넣는다 (AI가 꺼져 있어도)."""

    def setUp(self):
        import travel.chat as chat
        from tests.test_offline import _place
        self.chat = chat
        self.fests = [
            _place("f1", "노상놀이야", content_type_id="15", ctype="축제", addr="전북 전주시 완산구", event_start="20260418", event_end="20261031"),
            _place("f2", "전라관찰사의 탄생", content_type_id="15", ctype="축제", addr="전북 전주시 완산구", event_start="20261018", event_end="20261129"),
        ]
        sights = [_place(str(i), f"명소{i}", addr="전북 전주시 덕진구", mapx=str(127.1 + i * 0.001)) for i in range(40)]

        def fake_gather(sido, area, start, end, include_food, today):
            return {"sido": sido, "area": area, "start": start.isoformat(), "end": end.isoformat(), "include_food": include_food,
                    "places": [dict(p, related_news_ids=[]) for p in sights], "news": [], "weather": [], "weather_status": "out_of_range",
                    "air": {"by_date": {}, "realtime": None, "warnings": []}, "warnings": [], "fetched_at": __import__("time").time()}

        for p in [patch.object(chat, "chat_json_messages", side_effect=RuntimeError("ollama down")),
                  patch.object(chat, "gather_raw", side_effect=fake_gather), patch.object(chat, "enrich", return_value=[]),
                  patch.object(chat, "_collect_festivals", return_value=(self.fests, []))]:
            p.start()
            self.addCleanup(p.stop)
        self.session = chat.ChatSession()

    def say(self, text):
        return self.chat.handle_message(self.session, text, today=date(2026, 10, 21), ranker=FakeRanker())

    def visits(self, r):
        return [[e["place"]["name"] for e in d["events"] if e["kind"] == "visit"] for d in r["plan"]]

    def test_province_group_is_asked_once_then_city_works(self):
        r = self.say("전라도 여행 다음주 주말에 4박 5일로 일정 짜줘")
        self.assertIn("전북·전남·광주", r["reply"])
        self.assertNotIn("어느 지역으로 가실 건가요", r["reply"])
        r = self.say("전주")
        self.assertEqual((r["slots"]["region"], r["slots"]["area"]), ("전북", "전주"))
        self.assertEqual((r["slots"]["start_date"], r["slots"]["end_date"]), ("2026-10-31", "2026-11-04"))

    def test_plan_again_around_the_listed_festivals_without_ai(self):
        self.say("전주 다음주 주말에 4박 5일 혼자 여행 일정 짜줘")
        r = self.say("그 기간에 축제가 뭐가 있어?")
        self.assertEqual(r["intent"], "festival")
        for text in ["저거 기준으로 다시 짜줘", "축제 방문 기준으로 일정 짜줘"]:
            with self.subTest(text=text):
                r = self.say(text)
                self.assertNotIn("반영하지 못했어요", r["reply"])
                v = self.visits(r)
                self.assertIn("노상놀이야", v[0])          # 10/31 에 끝나는 축제 → 1일차
                self.assertIn("전라관찰사의 탄생", v[1])    # 다음 날
                self.assertTrue(all(3 <= len(d) <= 5 for d in v), v)
                flat = [x for d in v for x in d]
                self.assertEqual(len(flat), len(set(flat)))
                self.say("그 기간에 축제가 뭐가 있어?")    # 다음 문장도 목록 직후로 맞춘다

    def test_generic_words_do_not_pin_festivals_later(self):
        self.say("전주 다음주 주말에 4박 5일 혼자 여행 일정 짜줘")
        self.say("그 기간에 축제가 뭐가 있어?")
        self.say("고마워")
        r = self.say("실내 기준으로 바꿔줘")
        self.assertNotIn("축제 기간에 맞춰", r["reply"])


if __name__ == "__main__":
    unittest.main()
