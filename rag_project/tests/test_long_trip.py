"""
긴 일정(최대 30일)을 며칠씩 나눠 AI에 보내고, AI가 비운 자리를 채우는지 확인하는 오프라인 테스트.

    python -m unittest tests.test_long_trip -v
"""
import json
import re
import unittest
from datetime import date
from unittest.mock import patch

from tests.test_offline import FakeRanker, _place

TODAY = date(2026, 10, 6)  # 화요일


class LongTripTests(unittest.TestCase):
    N_PLACES = 60

    def setUp(self):
        import travel.chat as chat
        self.chat = chat
        self.prompts: list[str] = []
        self.per_day = 3      # 가짜 AI가 하루에 넣을 장소 수
        self.fail_groups: set[int] = set()  # 이 순번의 AI 호출은 실패시킨다
        self.pick_last = False  # True면 후보 목록 뒤쪽부터 고른다 (수정 요청에서 원래 장소 대신 새 장소를 고르는 AI 흉내)

        def fake_llm(messages, temperature=0.3):
            if messages[0]["content"].startswith("너는 여행 플래너 챗봇의 '정보 추출기'"):
                return {}, "{}"
            user = messages[-1]["content"]
            self.prompts.append(user)
            if len(self.prompts) - 1 in self.fail_groups:
                raise RuntimeError("ollama down")
            # 프롬프트에 실린 후보와 날짜만 써서 답한다 (실제 AI처럼)
            cands = re.findall(r"^(C\d+) \|", user, re.M)
            if self.pick_last:
                cands.reverse()
            m = re.search(r"\[출력할 날짜\][^\n]*\n([^\n]+)", user)
            dates = m.group(1).split(", ") if m else re.findall(r"^- (\d{4}-\d{2}-\d{2})", user.split("[후보 장소]")[0], re.M)
            days = []
            for d in dates:
                items = [{"candidate_id": cands.pop(0), "note": ""} for _ in range(self.per_day) if cands]
                days.append({"date": d, "theme": "", "items": items})
            plan = {"message": "일정이에요.", "follow_up": "", "days": days}
            return plan, json.dumps(plan)

        def fake_gather(sido, area, start, end, include_food, today):
            places = [_place(str(i), f"명소{i}", mapx=str(129.0 + i * 0.001)) for i in range(self.N_PLACES)]
            places += [_place(f"r{i}", f"식당{i}", content_type_id="39", ctype="음식점") for i in range(40)]
            for p in places:
                p["related_news_ids"] = []
            return {
                "sido": sido, "area": area, "start": start.isoformat(), "end": end.isoformat(),
                "include_food": include_food, "places": places, "news": [], "weather": [], "weather_status": "out_of_range",
                "air": {"by_date": {}, "realtime": None, "warnings": []}, "warnings": [], "fetched_at": __import__("time").time(),
            }

        self.patches = [
            patch.object(chat, "CHAT_EXTRACT_LLM_MIN_CHARS", 0),
            patch.object(chat, "CHAT_MAX_CANDIDATES", 10),  # .env 값이 작아도 모든 날이 채워져야 한다
            patch.object(chat, "CHAT_PLAN_CHUNK_DAYS", 3),
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

    def visits(self, r):
        return [[e["place"]["name"] for e in d["events"] if e["kind"] == "visit"] for d in r["plan"]]

    def test_three_days_fit_in_one_call_with_small_candidate_limit(self):
        r = self.say("부산 10월 10일부터 2박3일 혼자 갈래")
        self.assertEqual(len(self.prompts), 1)
        self.assertEqual(len(r["plan"]), 3)
        self.assertTrue(all(len(v) >= 3 for v in self.visits(r)), self.visits(r))
        self.assertGreaterEqual(len(re.findall(r"^C\d+ \|", self.prompts[0], re.M)), 17)  # 3일×5+2

    def test_two_weeks_are_split_and_every_day_is_filled(self):
        r = self.say("부산 10월 10일부터 13박 14일 혼자 갈래")
        self.assertEqual(r["slots"]["end_date"], "2026-10-23")
        self.assertEqual(len(self.prompts), 5)  # 3+3+3+3+2일
        visits = self.visits(r)
        self.assertEqual(len(visits), 14)
        self.assertTrue(all(len(v) >= 3 for v in visits), visits)
        flat = [x for v in visits for x in v]
        self.assertEqual(len(flat), len(set(flat)))  # 여러 묶음에 걸쳐도 같은 장소를 두 번 쓰지 않음
        self.assertIn("[출력할 날짜]", self.prompts[1])

    def test_thin_and_failed_days_are_filled_from_remaining_candidates(self):
        self.per_day = 1
        self.fail_groups = {1}
        r = self.say("부산 10월 10일부터 6박 7일 혼자 갈래")
        visits = self.visits(r)
        self.assertEqual(len(visits), 7)
        self.assertTrue(all(len(v) >= 3 for v in visits), visits)

    def test_unreachable_ai_is_called_once_and_days_are_filled_by_rules(self):
        self.fail_groups = {0, 1, 2}
        r = self.say("부산 10월 10일부터 6박 7일 혼자 갈래")
        self.assertEqual(len(self.prompts), 1)  # 연결이 안 되면 나머지 묶음은 부르지 않는다
        self.assertTrue(all(len(v) >= 3 for v in self.visits(r)), self.visits(r))

    def test_modify_one_day_of_long_trip_only_calls_ai_for_that_day(self):
        self.say("부산 10월 10일부터 6박 7일 혼자 갈래")
        before = self.visits({"plan": self.session.view["plan"]})
        self.prompts.clear()
        self.pick_last = True
        r = self.say("5일차 다른 곳으로 바꿔줘")
        self.assertEqual(len(self.prompts), 1)
        self.assertIn("2026-10-14", self.prompts[0].split("[출력할 날짜]")[1])
        after = self.visits(r)
        self.assertEqual(after[:4] + after[5:], before[:4] + before[5:])  # 다른 날은 그대로
        self.assertNotEqual(after[4], before[4])

    def test_week_words_are_durations(self):
        from travel.dates import parse_trip_dates
        for text, nights in [("부산 일주일 일정", 6), ("제주 2주 여행", 13), ("강릉 열흘", 9), ("다음 주 금요일", None)]:
            self.assertEqual(parse_trip_dates(text, TODAY)["nights"], nights, text)

    def test_every_length_from_1_to_30_days(self):
        self.N_PLACES = 160
        for nights in range(0, 30):
            with self.subTest(nights=nights):
                s = self.chat.ChatSession()
                text = f"부산 10월 10일부터 {nights}박 {nights + 1}일 혼자 갈래" if nights else "부산 10월 10일 당일치기 혼자 갈래"
                r = self.chat.handle_message(s, text, today=TODAY, ranker=self.ranker)
                visits = self.visits(r)
                self.assertEqual(len(visits), nights + 1)
                self.assertTrue(all(3 <= len(v) <= 6 for v in visits), visits)
                flat = [x for v in visits for x in v]
                self.assertEqual(len(flat), len(set(flat)))

    def test_month_word(self):
        from travel.dates import parse_trip_dates
        self.assertEqual(parse_trip_dates("제주 한 달 살기 일정", TODAY)["nights"], 29)

    def test_small_area_is_topped_up_with_nearby_places(self):
        self.N_PLACES = 10  # 그 군 안의 장소가 10곳뿐
        nearby = [_place(f"n{i}", f"주변명소{i}", addr="부산 기장군", mapx=str(129.2 + i * 0.001)) for i in range(80)]
        with patch.object(self.chat, "_collect_candidates", return_value=(nearby, [])) as m:
            r = self.say("부산 기장 10월 10일부터 9박 10일 혼자 갈래")
        self.assertEqual(m.call_args.args[4], "")  # 시도 전체에서 보충
        visits = self.visits(r)
        self.assertEqual(len(visits), 10)
        self.assertTrue(all(len(v) >= 3 for v in visits), visits)
        flat = [x for v in visits for x in v]
        self.assertTrue(all(f"명소{i}" in flat for i in range(10)))  # 그 지역 장소를 먼저 다 쓴다
        self.assertTrue(any("가까운 부산 지역" in c for c in r["caveats"]))

    def test_too_long_is_rejected(self):
        r = self.say("부산 10월 10일부터 30박 31일")
        self.assertIn("최대 30일", r["reply"])

    def test_declared_length_wins_over_weekend(self):
        # "창원 4박 5일" 다음에 "이번 주말"이라고 답해도 토~일(1박 2일)로 줄지 않는다
        self.say("창원 4박 5일 일정 짜줘")
        r = self.say("이번 주말에 혼자 갈래")
        self.assertEqual((r["slots"]["start_date"], r["slots"]["end_date"]), ("2026-10-10", "2026-10-14"))
        self.assertEqual(len(r["plan"]), 5)
        s = self.chat.ChatSession()
        r = self.chat.handle_message(s, "이번 주말 창원 4박5일 혼자 일정 짜줘", today=TODAY, ranker=self.ranker)
        self.assertEqual(r["slots"]["end_date"], "2026-10-14")
        s = self.chat.ChatSession()
        r = self.chat.handle_message(s, "창원 이번 주말 혼자 여행 짜줘", today=TODAY, ranker=self.ranker)
        self.assertEqual(r["slots"]["end_date"], "2026-10-11")  # 기간을 안 말하면 주말은 토~일


if __name__ == "__main__":
    unittest.main()
