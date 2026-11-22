"""숙소 체크인·체크아웃 시간: 숙소를 알려주면 한 번 물어보고, 알려주면 일정에 반영한다."""
import unittest
from datetime import date

from travel.clock import hhmm, parse_stay_times
from tests.test_userplaces import FlowBase, HOTEL


class ParseStayTimesTests(unittest.TestCase):
    def test_both_times(self):
        self.assertEqual(parse_stay_times("체크인은 오후 3시, 체크아웃은 11시야"), ({"in": 15 * 60, "out": 11 * 60}, ""))

    def test_time_before_keyword_and_clock_format(self):
        self.assertEqual(parse_stay_times("3시에 체크인하고 다음날 11시 체크아웃")[0], {"in": 15 * 60, "out": 11 * 60})
        self.assertEqual(parse_stay_times("체크인 15:00 체크아웃 오전 10시 30분")[0], {"in": 15 * 60, "out": 10 * 60 + 30})

    def test_the_rest_of_the_sentence_is_kept(self):
        times, rest = parse_stay_times("체크인 4시 체크아웃 11시 혼자 갈 거야")
        self.assertEqual(times, {"in": 16 * 60, "out": 11 * 60})
        self.assertEqual(rest, "혼자 갈 거야")

    def test_checkout_early_morning_is_not_pm(self):
        self.assertEqual(parse_stay_times("체크아웃 8시")[0], {"out": 8 * 60})

    def test_no_time_no_result(self):
        self.assertEqual(parse_stay_times("체크인 시간은 몰라"), ({}, "체크인 시간은 몰라"))
        self.assertEqual(parse_stay_times("상관없어요"), ({}, "상관없어요"))


class StayTimesFlowTests(FlowBase):
    DB = {"스타호텔": [HOTEL]}

    def plan_with_hotel(self):
        return self.say("전주 다음주 주말에 2박 3일 혼자 여행인데 숙소는 판교 스타호텔로 예약했어. 숙소 주변으로 동선 짜줘")

    def test_defaults_are_fixed_and_the_user_is_told_where_to_change_them(self):
        r = self.plan_with_hotel()
        self.assertIn("체크인은 첫날 15:00, 체크아웃은 마지막 날 11:00", r["reply"])
        self.assertIn("여행 일정 상세 페이지", r["reply"])                          # 바꾸는 곳을 알려준다
        self.assertNotIn("알려주세요", r["reply"])                                  # 시간을 되묻지 않는다
        r2 = self.say("이 날 실내로 바꿔줘")
        self.assertNotIn("체크인은 첫날", r2["reply"])                              # 안내는 한 번만

    def test_the_optional_question_does_not_ask_about_check_in(self):
        r = self.say("전주 다음주 주말에 2박 3일 여행인데 숙소는 판교 스타호텔로 예약했어")
        self.assertEqual(r["stage"], "asking")
        self.assertIn("누구와 함께", r["reply"])
        self.assertNotIn("체크인", r["reply"].split("누구와 함께")[1])
        r = self.say("혼자, 체크인 오후 4시 체크아웃 오전 10시")
        self.assertIsNotNone(r["plan"])
        self.assertEqual(self.session.stay_times, {"in": 16 * 60, "out": 10 * 60})
        self.assertNotIn("체크인", self.session.slots["preferences"])            # 취향으로 저장되지 않는다
        self.assertIn("체크인 16:00 · 체크아웃 10:00", r["reply"])
        self.assertEqual([e["start"] for e in r["plan"][0]["events"] if e["kind"] == "stay" and e["label"] == "체크인"], ["16:00"])

    def test_times_given_later_rearrange_the_plan(self):
        r = self.plan_with_hotel()
        r2 = self.say("체크인은 오후 3시, 체크아웃은 오전 11시야")
        self.assertIn("체크인 15:00 · 체크아웃 11:00", r2["reply"])
        d0, dl = r2["plan"][0]["events"], r2["plan"][-1]["events"]
        checkin = [e for e in d0 if e["kind"] == "stay" and e["label"] == "체크인"]
        self.assertEqual(len(checkin), 1)
        self.assertEqual(checkin[0]["start"], "15:00")                          # 일정 사이에 15시 체크인
        self.assertEqual(d0[0]["kind"], "stay")
        self.assertEqual(d0[0]["label"], "짐 맡기고 출발")
        self.assertIn("체크아웃 (11:00까지)", dl[0]["label"])
        for d in r2["plan"]:
            for a, b in zip(d["events"], d["events"][1:]):
                self.assertLessEqual(a["end"], b["start"], (a, b))
        self.assertIn("체크인", r2["reply"])

    def test_early_checkout_moves_the_last_day_start_earlier(self):
        self.plan_with_hotel()
        r = self.say("체크아웃 9시")
        self.assertEqual(r["plan"][-1]["events"][0]["start"], "09:00")

    def test_without_a_lodging_nothing_is_asked(self):
        r = self.make_plan()
        self.assertNotIn("체크인", r["reply"])


if __name__ == "__main__":
    unittest.main()
