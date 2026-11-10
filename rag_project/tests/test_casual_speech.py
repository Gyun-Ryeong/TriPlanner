"""대충 말해도 알아듣기: 줄임말·대충 쓴 날짜 (AI 없이 규칙만으로)"""
import unittest
from datetime import date
from unittest.mock import patch

import travel.chat as c
from travel.dates import parse_trip_dates

TODAY = date(2026, 11, 9)  # 월요일


def d(s):
    return date.fromisoformat(s)


class CasualDateTests(unittest.TestCase):
    def check(self, text, start=None, end=None, nights=None):
        r = parse_trip_dates(text, TODAY)
        self.assertEqual((r["start"], r["end"], r["nights"]),
                         (d(start) if start else None, d(end) if end else None, nights), text)

    def test_slang(self):
        self.check("낼부터 이틀", "2026-11-10", None, 1)
        self.check("여수 낼모레 1박2일", "2026-11-11", None, 1)
        self.check("담주 금욜부터", "2026-11-20")
        self.check("이번주 토욜", "2026-11-14")
        self.check("전주 담주 토욜 당일", "2026-11-21", None, 0)

    def test_weekday_runs(self):
        self.check("강릉 금토일", "2026-11-13", "2026-11-15")
        self.check("담주 토일 경주", "2026-11-21", "2026-11-22")
        self.check("다음주 금토", "2026-11-20", "2026-11-21")
        self.check("일월저수지 가고 싶어")  # 요일이 아님
        self.check("월 화 수 목 금", "2026-11-09", "2026-11-13")
        self.check("월화수목금", "2026-11-09", "2026-11-13")
        self.check("금 토 일", "2026-11-13", "2026-11-15")
        self.check("토,일", "2026-11-14", "2026-11-15")
        self.check("금토일월", "2026-11-13", "2026-11-16")
        self.check("월~금", "2026-11-09", "2026-11-13")
        self.check("다음주 월-금", "2026-11-16", "2026-11-20")
        self.check("금부터 일까지", "2026-11-13", "2026-11-15")
        self.check("금 출발", "2026-11-13")
        self.check("12월 화 아무때나")  # "12월"의 "월"과 "화"를 월~화로 보지 않는다
        self.check("금 2개 사러")

    def test_month_words(self):
        self.check("다음달 5일부터", "2026-12-05")
        self.check("부산 2박3일 다음달 초", "2026-12-01", None, 2)
        self.check("담달 중순에 제주 3박", "2026-12-11", None, 3)
        self.check("제주 3박4일 12월 초에", "2026-12-01", None, 3)
        self.check("부산 이번달 말에 2박", "2026-11-25", None, 2)

    def test_day_only(self):
        self.check("부산 2박 3일 20일부터", "2026-11-20", None, 2)
        self.check("20일부터 22일까지", "2026-11-20", "2026-11-22")
        self.check("25일 출발", "2026-11-25")
        self.check("8일부터", "2026-12-08")  # 이번 달 8일은 지났다
        self.check("포항 3일", None, None, 2)
        self.check("오늘부터 7일", "2026-11-09", None, 6)
        self.check("3일차 바꿔줘")

    def test_holidays(self):
        self.check("부산 크리스마스에 2박", "2026-12-25", None, 2)
        self.check("어린이날 경주 당일치기", "2027-05-05", None, 0)
        self.check("크리스마스 분위기 나는 곳")  # 날짜가 아님
        self.check("크리스마스 마켓 가고싶어")


class CasualChatTests(unittest.TestCase):
    def run_chat(self, *msgs):
        s = c.ChatSession()
        with patch.object(c, "_llm_extract", return_value=None), \
             patch.object(c, "_make_plan", side_effect=lambda session, *a, **k: setattr(session, "plan", {"days": []}) or "PLAN"), \
             patch.object(c, "_answer_list", return_value=("LIST", {}, [])):
            replies = [c.handle_message(s, m, today=TODAY)["reply"] for m in msgs]
        return s.slots, replies

    def test_multi_turn_slang(self):
        slots, _ = self.run_chat("부산 ㄱㄱ", "담주 금욜부터", "2박")
        self.assertEqual((slots["start_date"], slots["end_date"]), ("2026-11-20", "2026-11-22"))

    def test_day_answer_after_length(self):
        slots, _ = self.run_chat("부산 2박", "20일")  # 기간을 안 뒤 "20일" = 날짜
        self.assertEqual((slots["start_date"], slots["end_date"]), ("2026-11-20", "2026-11-22"))

    def test_week_after_next(self):
        r = parse_trip_dates("다다음주 금요일", TODAY)
        self.assertEqual(r["start"], d("2026-11-27"))
        r = parse_trip_dates("다다음주 주말", TODAY)
        self.assertEqual((r["start"], r["end"]), (d("2026-11-28"), d("2026-11-29")))
        r = parse_trip_dates("다음다음주 월~금", TODAY)
        self.assertEqual((r["start"], r["end"]), (d("2026-11-23"), d("2026-11-27")))
        self.assertEqual(parse_trip_dates("다다음달 5일", TODAY)["start"], d("2027-01-05"))

    def test_month_only_asks_day(self):
        slots, replies = self.run_chat("다음달 부산 2박", "5일")
        self.assertIn("12월 며칠", replies[0])
        self.assertEqual((slots["start_date"], slots["end_date"]), ("2026-12-05", "2026-12-07"))

    def test_month_only_then_length_then_day(self):
        slots, _ = self.run_chat("다음달 여수", "2박3일", "10일")  # "2박3일"의 3일은 날짜가 아님
        self.assertEqual((slots["start_date"], slots["end_date"]), ("2026-12-10", "2026-12-12"))

    def test_month_only_then_range(self):
        slots, _ = self.run_chat("12월에 제주 가고싶어", "20일부터 22일까지")
        self.assertEqual((slots["start_date"], slots["end_date"]), ("2026-12-20", "2026-12-22"))

    def test_week_only_asks_weekday(self):
        slots, replies = self.run_chat("다음주 강릉 1박", "금요일")
        self.assertIn("무슨 요일", replies[0])
        self.assertEqual((slots["start_date"], slots["end_date"]), ("2026-11-20", "2026-11-21"))
        slots, _ = self.run_chat("다다음주 경주 2박", "토")
        self.assertEqual(slots["start_date"], "2026-11-28")
        slots, _ = self.run_chat("다음주 부산", "금토일")
        self.assertEqual((slots["start_date"], slots["end_date"]), ("2026-11-20", "2026-11-22"))

    def test_this_and_last_week(self):
        wed = date(2026, 11, 11)
        cases = {"이번 주 금요일": ("2026-11-13", None), "이번 주 토일": ("2026-11-14", "2026-11-15"),
                 "저번 주 금요일": ("2026-11-06", None), "지난주 토요일": ("2026-11-07", None),
                 "지난 주말": ("2026-11-07", "2026-11-08"), "저저번주 금요일": ("2026-10-30", None),
                 "지난달 5일": ("2026-10-05", None)}
        for text, (st, en) in cases.items():
            r = parse_trip_dates(text, wed)
            self.assertEqual((r["start"], r["end"]), (d(st), d(en) if en else None), text)
        self.assertIsNone(parse_trip_dates("전주 1박2일", wed)["start"])  # 도시 '전주'는 날짜가 아님

    def test_yesterday_today(self):
        wed = date(2026, 11, 11)
        cases = {"오늘": ("2026-11-11", None), "어제": ("2026-11-10", None), "그제": ("2026-11-09", None),
                 "그저께": ("2026-11-09", None), "엊그제": ("2026-11-08", None),
                 "오늘내일": ("2026-11-11", "2026-11-12"), "내일모레": ("2026-11-13", None)}
        for text, (st, en) in cases.items():
            r = parse_trip_dates(text, wed)
            self.assertEqual((r["start"], r["end"]), (d(st), d(en) if en else None), text)

    def test_yesterday_is_past(self):
        s = c.ChatSession()
        with patch.object(c, "_llm_extract", return_value=None):
            c.handle_message(s, "부산 2박", today=date(2026, 11, 11))
            r = c.handle_message(s, "어제부터", today=date(2026, 11, 11))
        self.assertIn("이미 지났어요", r["reply"])

    def test_last_week_is_past(self):
        s = c.ChatSession()
        with patch.object(c, "_llm_extract", return_value=None):
            c.handle_message(s, "부산 2박", today=date(2026, 11, 11))
            r = c.handle_message(s, "지난주", today=date(2026, 11, 11))
        self.assertIn("이미 지났어요", r["reply"])
        self.assertEqual(s.slots["start_date"], "")

    def test_where_to_go_is_recommendation(self):
        _, replies = self.run_chat("대구 놀러가고싶은데 어디가 좋음?")
        self.assertTrue(replies[0].startswith("LIST"))

    def test_leftover_has_no_particle(self):
        slots, _ = self.run_chat("주말에 바다 보러 가고싶음")
        self.assertEqual(slots["preferences"], "바다 보러 가고싶음")

    def test_same_region_and_area_named_once(self):
        _, replies = self.run_chat("제주 3박4일")
        self.assertNotIn("제주 제주", replies[0])


if __name__ == "__main__":
    unittest.main()
