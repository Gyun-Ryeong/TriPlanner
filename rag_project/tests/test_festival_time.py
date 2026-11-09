"""
축제 시간 처리 오프라인 테스트: 사용자가 알려준 시각 읽기 → 그 시각을 고정한 시간표 → 대화 흐름(안내 → 시간 입력 → 재조율).

    python -m unittest tests.test_festival_time -v
"""
import unittest
from datetime import date
from unittest.mock import patch

from tests.test_offline import FakeRanker, _place


def mins(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


class ClockTests(unittest.TestCase):
    def test_parses_common_korean_expressions(self):
        from travel.clock import parse_time_range as p
        self.assertEqual(p("저녁 7시부터 9시까지"), (19 * 60, 21 * 60))
        self.assertEqual(p("19:00~21:00"), (19 * 60, 21 * 60))
        self.assertEqual(p("오후 7시 30분"), (19 * 60 + 30, None))
        self.assertEqual(p("7시 반"), (19 * 60 + 30, None))
        self.assertEqual(p("오전 10시부터 오후 2시"), (10 * 60, 14 * 60))
        self.assertEqual(p("낮 1시에 시작해서 3시에 끝나"), (13 * 60, 15 * 60))
        self.assertEqual(p("불꽃축제 20시"), (20 * 60, None))

    def test_not_a_clock_time(self):
        from travel.clock import parse_time_range as p
        for t in ("2박 3일 일정 짜줘", "3시간 정도 걸려요", "10월 10일 부산", "축제 알려줘"):
            self.assertIsNone(p(t), t)


def P(i, title, lat, lon, ty="12", indoor=False):
    return {"content_id": str(i), "title": title, "mapy": str(lat), "mapx": str(lon), "content_type_id": ty,
            "content_type": "관광지", "addr": "", "indoor": indoor}


class AnchoredTimelineTests(unittest.TestCase):
    FEST = P(99, "불꽃축제", 35.100, 129.100, "15")
    FREE = [P(1, "A", 35.101, 129.101), P(2, "B", 35.102, 129.102), P(3, "C", 35.103, 129.103)]
    REST = [P(10, "식당1", 35.101, 129.101, "39"), P(11, "식당2", 35.102, 129.101, "39"), P(12, "식당3", 35.100, 129.101, "39")]

    def build(self, fixed, places=None):
        from travel.schedule import build_timeline
        items = [{"place": p, "note": ""} for p in (self.FREE if places is None else places)]
        items.append({"place": self.FEST, "note": "", "fixed": fixed})
        return build_timeline(items, self.REST, set())

    def assert_clean(self, ev):
        for a, b in zip(ev, ev[1:]):
            self.assertLessEqual(a["end"], b["start"], (a, b))

    def test_evening_festival_keeps_its_time_and_dinner_comes_before(self):
        ev = self.build((19 * 60, 21 * 60))
        fest = next(e for e in ev if e["kind"] == "visit" and e["place"]["title"] == "불꽃축제")
        self.assertEqual((fest["start"], fest["end"], fest["fixed"]), ("19:00", "21:00", True))
        self.assert_clean(ev)
        dinner = [e for e in ev if e["kind"] == "meal" and e["label"] == "저녁"]
        self.assertEqual(len(dinner), 1)
        self.assertLessEqual(dinner[0]["end"], "19:00")
        before = [e for e in ev if e["kind"] == "visit" and e["place"]["title"] != "불꽃축제"]
        self.assertTrue(all(e["end"] <= "19:00" for e in before))      # 일반 장소는 축제 전에 끝난다
        self.assertEqual(ev[-1]["end"], "21:00")                       # 축제 뒤에 저녁을 또 넣지 않는다

    def test_festival_that_covers_lunch_replaces_lunch(self):
        ev = self.build((12 * 60, 14 * 60), places=[])
        self.assertEqual(ev[0]["start"], "12:00")                      # 첫 일정이 정해진 장소면 그 시각에 하루를 시작
        self.assertFalse([e for e in ev if e["kind"] == "meal" and e["label"] == "점심"])
        self.assert_clean(ev)

    def test_places_that_cannot_fit_before_are_placed_after_or_dropped_if_too_late(self):
        far_late = self.build((20 * 60, 22 * 60))
        self.assert_clean(far_late)
        late_visits = [e for e in far_late if e["kind"] == "visit" and e["start"] >= "20:30" and e["place"]["title"] != "불꽃축제"]
        self.assertEqual(late_visits, [])

    def test_without_fixed_time_nothing_changes(self):
        from travel.schedule import build_timeline
        ev = build_timeline([{"place": p, "note": ""} for p in self.FREE], self.REST, set())
        self.assertEqual(ev[0]["start"], "10:00")
        self.assertFalse(any(e.get("fixed") for e in ev))


class FestivalChatFlowTests(unittest.TestCase):
    def setUp(self):
        import travel.chat as chat
        self.chat = chat
        self.fests = [
            _place("f1", "노상놀이야", content_type_id="15", ctype="축제", addr="전북 전주시 완산구", event_start="20261018", event_end="20261231",
                   mapx="127.100", mapy="35.100"),
        ]
        sights = [_place(str(i), f"명소{i}", addr="전북 전주시 덕진구", mapx=str(127.1 + i * 0.001), mapy="35.101") for i in range(40)]
        sights += [_place("far", "아주먼곳", addr="전북 군산시", mapx="126.0", mapy="36.0")]

        def fake_gather(sido, area, start, end, include_food, today):
            return {"sido": sido, "area": area, "start": start.isoformat(), "end": end.isoformat(), "include_food": include_food,
                    "places": [dict(p, related_news_ids=[]) for p in self.fests + sights + [dict(_place(f"r{i}", f"식당{i}", content_type_id="39"),
                                                                                 content_type_id="39", mapx=str(127.1 + i * 0.001), mapy="35.101") for i in range(8)]],
                    "news": [], "weather": [], "weather_status": "out_of_range",
                    "air": {"by_date": {}, "realtime": None, "warnings": []}, "warnings": [], "fetched_at": __import__("time").time()}

        for p in [patch.object(chat, "chat_json_messages", side_effect=RuntimeError("ollama down")),
                  patch.object(chat, "gather_raw", side_effect=fake_gather), patch.object(chat, "enrich", return_value=[]),
                  patch.object(chat, "_collect_festivals", return_value=(self.fests, []))]:
            p.start()
            self.addCleanup(p.stop)
        self.session = chat.ChatSession()

    def say(self, text):
        return self.chat.handle_message(self.session, text, today=date(2026, 10, 21), ranker=FakeRanker())

    def make_plan(self):
        self.first = self.say("전주 다음주 주말에 2박 3일 혼자 여행 일정 짜줘")   # 축제가 일정에 들어가면 이때 시간 안내가 한 번 나간다
        return self.say("노상놀이야 축제 방문 기준으로 일정 짜줘")

    def fest_event(self, r):
        for di, d in enumerate(r["plan"]):
            for e in d["events"]:
                if e["kind"] == "visit" and e["place"]["name"] == "노상놀이야":
                    return di, e
        return None, None

    def test_plan_explains_that_the_user_must_find_the_festival_time(self):
        r = self.make_plan()
        self.assertIn("축제 시간은 저희가 알 수 없어요", self.first["reply"])
        self.assertIn("사용자님이 공식 홈페이지나 포스터에서 시간을 찾아서 알려주셔야", self.first["reply"])
        self.assertIn("노상놀이야 저녁 7시부터 9시", self.first["reply"])           # 예시 문장
        self.assertNotIn("축제 시간은 저희가 알 수 없어요", r["reply"])             # 같은 축제는 한 번만 안내
        di, e = self.fest_event(r)
        self.assertIsNotNone(e)
        self.assertFalse(e["fixed"])
        names = [x["place"]["name"] for x in r["plan"][di]["events"] if x["kind"] == "visit"]
        self.assertNotIn("아주먼곳", names)                           # 축제장에서 먼 장소는 그날 일정에 넣지 않는다

    def test_user_gives_time_and_the_rest_of_the_day_is_rearranged(self):
        r = self.make_plan()
        di, _ = self.fest_event(r)
        r2 = self.say("노상놀이야 저녁 7시부터 9시")
        self.assertEqual(r2["intent"], "plan")
        self.assertIn("19:00 ~ 21:00", r2["reply"])
        di2, e = self.fest_event(r2)
        self.assertEqual(di2, di)
        self.assertEqual((e["start"], e["end"], e["fixed"]), ("19:00", "21:00", True))
        self.assertIn("⏰ 시간 지정", r2["reply"])
        events = r2["plan"][di]["events"]
        for a, b in zip(events, events[1:]):
            self.assertLessEqual(a["end"], b["start"])
        self.assertNotIn("축제 시간은 저희가 알 수 없어요", r2["reply"])   # 안내는 한 번만

    def test_short_answer_right_after_the_notice_is_accepted(self):
        self.make_plan()
        r = self.say("저녁 7시부터 9시")
        self.assertIn("19:00 ~ 21:00", r["reply"])

    def test_start_only_uses_default_stay(self):
        self.make_plan()
        r = self.say("노상놀이야 20시")
        _, e = self.fest_event(r)
        self.assertEqual((e["start"], e["end"]), ("20:00", "22:00"))

    def test_time_is_kept_when_the_plan_is_modified_later_and_unrelated_times_are_ignored(self):
        self.make_plan()
        self.say("노상놀이야 저녁 7시부터 9시")
        r = self.say("1일차 오전 10시에 출발할게")                       # 축제와 무관한 시각: 축제 시간을 바꾸지 않는다
        _, e = self.fest_event(r) if r.get("plan") else (None, None)
        if e:
            self.assertEqual(e["start"], "19:00")


if __name__ == "__main__":
    unittest.main()
