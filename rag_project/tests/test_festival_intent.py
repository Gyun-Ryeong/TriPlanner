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


if __name__ == "__main__":
    unittest.main()
