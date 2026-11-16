"""동선 최적화: 하루 안 가장 짧은 순서 + 날짜 사이 장소 맞바꾸기"""
import unittest

from travel.geo import best_order, route_km
from travel.routing import rebalance_days


def P(cid, lat, lon, indoor=False):
    return {"content_id": str(cid), "title": f"P{cid}", "mapy": str(lat), "mapx": str(lon),
            "content_type_id": "14" if indoor else "12", "indoor": indoor}


class BestOrderTests(unittest.TestCase):
    def test_beats_nearest_neighbour(self):
        # 가까운 곳 잇기(첫 장소 고정)는 A→B→C→D→E처럼 왔다 갔다 하지만, 가장 짧은 길은 한쪽 끝에서 시작한다
        pts = [P(1, 37.50, 127.00), P(2, 37.50, 127.02), P(3, 37.50, 126.97), P(4, 37.50, 127.05), P(5, 37.50, 126.93)]
        items = [{"place": p} for p in pts]
        out = [it["place"] for it in best_order(items)]
        naive = route_km(pts[:1] + sorted(pts[1:], key=lambda p: abs(float(p["mapx"]) - 127.0)))
        self.assertLess(route_km(out), naive)
        self.assertIn([p["title"] for p in out], (["P5", "P3", "P1", "P2", "P4"], ["P4", "P2", "P1", "P3", "P5"]))  # 한쪽 끝부터 한 줄로

    def test_many_places_use_two_opt(self):
        pts = [P(i, 37.5, 127.0 + (i * 7 % 10) / 100) for i in range(10)]  # 10곳: 근사 방식
        out = [it["place"] for it in best_order([{"place": p} for p in pts])]
        self.assertAlmostEqual(route_km(out), route_km(sorted(pts, key=lambda p: float(p["mapx"]))), places=3)

    def test_places_without_coords_go_last(self):
        a, b, none = P(1, 37.5, 127.0), P(2, 37.5, 127.01), {"title": "좌표없음", "mapx": "", "mapy": ""}
        out = best_order([{"place": none}, {"place": a}, {"place": b}])
        self.assertEqual(out[-1]["place"]["title"], "좌표없음")


class RebalanceTests(unittest.TestCase):
    def setUp(self):
        # 북쪽 2곳, 남쪽 2곳이 날마다 섞여 있다
        self.cand = {"N1": P(1, 37.60, 127.00), "N2": P(2, 37.61, 127.01),
                     "S1": P(3, 37.40, 127.00), "S2": P(4, 37.41, 127.01, indoor=True)}
        self.good = [{"outdoor_ok": True}, {"outdoor_ok": True}]

    def days(self, *groups):
        return [{"theme": "", "items": [{"candidate_id": c, "note": ""} for c in g]} for g in groups]

    def ids(self, days):
        return [sorted(it["candidate_id"] for it in d["items"]) for d in days]

    def test_groups_nearby_places_on_same_day(self):
        days = self.days(["N1", "S1"], ["S2", "N2"])
        self.assertEqual(rebalance_days(days, self.cand, self.good), 1)
        self.assertIn(self.ids(days), (
            [["N1", "N2"], ["S1", "S2"]], [["S1", "S2"], ["N1", "N2"]]))

    def test_outdoor_place_not_moved_to_bad_weather_day(self):
        days = self.days(["N1", "S2"], ["S1", "N2"])
        bad = [{"outdoor_ok": True}, {"outdoor_ok": False}]
        rebalance_days(days, self.cand, bad)
        # 2일차(궂은 날)로 갈 수 있는 건 실내(S2)뿐 → N1이 2일차로 가는 바꾸기는 없다
        self.assertNotIn("N1", self.ids(days)[1])

    def test_frozen_place_stays(self):
        days = self.days(["N1", "S1"], ["S2", "N2"])
        rebalance_days(days, self.cand, self.good, frozen={"N1", "N2"})
        self.assertEqual(self.ids(days), [["N1", "S1"], ["N2", "S2"]])  # S1↔S2는 바꿔도 나아지지 않아 그대로

    def test_already_compact_is_untouched(self):
        days = self.days(["N1", "N2"], ["S1", "S2"])
        self.assertEqual(rebalance_days(days, self.cand, self.good), 0)


if __name__ == "__main__":
    unittest.main()
