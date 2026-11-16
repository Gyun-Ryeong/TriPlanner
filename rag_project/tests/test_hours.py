"""영업시간·휴무일: 휴무 문구 읽기, 휴무일에 들어간 장소 고치기, 운영시간 밖 안내"""
import unittest
from datetime import date

from travel.hours import closed_on, open_range
from travel.planner import _out_of_hours
from travel.routing import fix_closures, rebalance_days

MON, TUE, SUN = date(2026, 11, 16), date(2026, 11, 17), date(2026, 11, 22)


def P(cid, rest="", hours="", ctype="14", lat=37.5, lon=127.0, indoor=True):
    key = {"14": ("usetimeculture", "restdateculture"), "12": ("usetime", "restdate"), "39": ("opentimefood", "restdatefood")}[ctype]
    intro = {k: v for k, v in zip(key, (hours, rest)) if v}
    return {"content_id": str(cid), "title": f"P{cid}", "content_type_id": ctype, "mapy": str(lat), "mapx": str(lon),
            "indoor": indoor, "intro": intro}


class ClosedOnTests(unittest.TestCase):
    def test_weekly(self):
        self.assertTrue(closed_on(P(1, "매주 월요일"), MON))
        self.assertFalse(closed_on(P(1, "매주 월요일"), TUE))
        self.assertTrue(closed_on(P(1, "매주 화요일 / 수요일"), TUE))
        self.assertTrue(closed_on(P(1, "월·화요일"), TUE))
        self.assertTrue(closed_on(P(1, "월요일(공휴일인 경우 다음날)"), MON))

    def test_open_all_year_or_unknown(self):
        self.assertFalse(closed_on(P(1, "연중무휴"), MON))
        self.assertFalse(closed_on(P(1, "연중무휴※ 장날 다음날 휴무 가능성 있으므로 전화 후 방문"), MON))
        self.assertFalse(closed_on(P(1, ""), MON))
        self.assertFalse(closed_on({"title": "정보없음"}, MON))

    def test_nth_week(self):
        p = P(1, "매월 둘째, 넷째 주 월요일")
        self.assertFalse(closed_on(p, date(2026, 11, 2)))   # 첫째 주
        self.assertTrue(closed_on(p, date(2026, 11, 9)))    # 둘째 주
        self.assertTrue(closed_on(p, date(2026, 11, 23)))   # 넷째 주
        self.assertTrue(closed_on(P(1, "매월 마지막 주 월요일"), date(2026, 11, 30)))

    def test_holidays(self):
        self.assertTrue(closed_on(P(1, "설·추석 연휴"), date(2027, 2, 8)))
        self.assertTrue(closed_on(P(1, "설날 및 추석 당일"), date(2026, 9, 25)))
        self.assertFalse(closed_on(P(1, "설날 및 추석 당일"), date(2026, 9, 24)))
        self.assertTrue(closed_on(P(1, "1월 1일"), date(2027, 1, 1)))
        self.assertFalse(closed_on(P(1, "시설 점검일 별도 공지"), date(2027, 2, 7)))  # '시설'의 '설'은 설날이 아니다

    def test_open_range(self):
        self.assertEqual(open_range(P(1, hours="09:00~18:00 (입장 마감 17:00)")), (540, 1080))
        self.assertEqual(open_range(P(1, hours="- 11:30~20:00 - 준비시간 14:30~17:30", ctype="39")), (690, 1200))
        self.assertEqual(open_range(P(1, hours="18:00~02:00")), (1080, 1560))
        self.assertIsNone(open_range(P(1, hours="상시 개방")))

    def test_out_of_hours_warning(self):
        p = P(1, hours="10:00~17:00")
        self.assertEqual(_out_of_hours(p, "10:30", "12:00"), "")
        self.assertIn("운영시간(10:00~17:00) 밖", _out_of_hours(p, "16:30", "18:00"))


class FixClosuresTests(unittest.TestCase):
    def cond(self, *days, bad=()):
        return [{"date": d.isoformat(), "outdoor_ok": i not in bad} for i, d in enumerate(days)]

    def plan(self, *groups):
        return [{"theme": "", "items": [{"candidate_id": c, "note": "메모"} for c in g]} for g in groups]

    def test_swaps_to_open_day(self):
        cand = {"M": P(1, "매주 월요일"), "A": P(2), "B": P(3), "C": P(4)}
        days = self.plan(["M", "A"], ["B", "C"])
        notes = fix_closures(days, cand, self.cond(MON, TUE))
        self.assertNotIn("M", [it["candidate_id"] for it in days[0]["items"]])
        self.assertIn("M", [it["candidate_id"] for it in days[1]["items"]])
        self.assertIn("휴무라 11/17(화)로 옮겼어요", notes[0])

    def test_replaces_with_unused_candidate_when_no_swap(self):
        cand = {"M": P(1, "매주 월요일"), "S": P(2)}
        days = self.plan(["M"])
        notes = fix_closures(days, cand, self.cond(MON))
        self.assertEqual([it["candidate_id"] for it in days[0]["items"]], ["S"])
        self.assertIn("P2(으)로 바꿨어요", notes[0])

    def test_drops_when_nothing_fits(self):
        cand = {"M": P(1, "매주 월요일"), "X": P(2, "매주 월요일")}
        days = self.plan(["M", "X"])
        notes = fix_closures(days, cand, self.cond(MON))
        self.assertEqual(days[0]["items"], [])
        self.assertEqual(len(notes), 2)

    def test_frozen_and_outdoor_rules(self):
        cand = {"M": P(1, "매주 월요일"), "O": P(2, ctype="12", indoor=False)}
        days = self.plan(["M"], ["O"])
        fix_closures(days, cand, self.cond(MON, TUE, bad=(0,)), frozen=set())
        # 실외(O)는 궂은 월요일로 못 오므로 맞바꾸지 않고, 바꿀 후보도 없어 뺀다
        self.assertEqual(days[0]["items"], [])
        days = self.plan(["M"])
        fix_closures(days, cand, self.cond(MON), frozen={"M"})
        self.assertEqual(days[0]["items"][0]["candidate_id"], "M")  # 사용자가 꼭 넣은 곳은 그대로

    def test_rebalance_never_moves_into_closed_day(self):
        # 가까이 모으려면 M을 1일차(월)로 보내야 하지만, 월요일 휴무라 보내지 않는다
        cand = {"M": P(1, "매주 월요일", lat=37.60), "N": P(2, lat=37.61), "S1": P(3, lat=37.40), "S2": P(4, lat=37.41)}
        days = self.plan(["N", "S1"], ["S2", "M"])
        rebalance_days(days, cand, self.cond(MON, TUE))
        self.assertNotIn("M", [it["candidate_id"] for it in days[0]["items"]])


if __name__ == "__main__":
    unittest.main()
