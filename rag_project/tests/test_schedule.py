"""시간표·이동·시군구 조회 오프라인 테스트."""
import unittest
from datetime import date
from unittest.mock import patch

from tests.test_offline import _place


def P(i, title, lat, lon, ty="12", addr="", indoor=False):
    return {"content_id": str(i), "title": title, "mapy": str(lat), "mapx": str(lon), "content_type_id": ty,
            "content_type": "관광지", "addr": addr, "indoor": indoor}


class GeoTests(unittest.TestCase):
    def test_walk_for_short_and_transit_car_for_long(self):
        from travel.geo import estimate_travel
        near = estimate_travel(P(1, "a", 37.380, 127.120), P(2, "b", 37.385, 127.125))
        self.assertTrue(near["text"].startswith("도보 약"))
        far = estimate_travel(P(1, "a", 37.380, 127.120), P(3, "c", 37.450, 127.150))
        self.assertRegex(far["text"], r"대중교통 약 \d+분 / 차량 약 \d+분")
        self.assertGreater(far["minutes"], near["minutes"])

    def test_missing_coordinates_do_not_crash(self):
        from travel.geo import estimate_travel
        e = estimate_travel(P(1, "a", 37.38, 127.12), {"title": "x", "mapx": "", "mapy": ""})
        self.assertEqual(e["minutes"], 20)
        self.assertIsNone(e["km"])

    def test_invalid_coordinates_are_ignored(self):
        from travel.geo import estimate_travel
        self.assertIsNone(estimate_travel(P(1, "a", 0, 0), P(2, "b", 37.4, 127.1))["km"])

    def test_nearest_neighbour_order(self):
        from travel.geo import order_by_proximity
        a, b, c = P(1, "A", 37.380, 127.120), P(2, "B", 37.450, 127.150), P(3, "C", 37.385, 127.125)
        out = order_by_proximity([{"place": a}, {"place": b}, {"place": c}])
        self.assertEqual([i["place"]["title"] for i in out], ["A", "C", "B"])  # 가까운 C가 먼저

    def test_district(self):
        from travel.geo import district_of
        self.assertEqual(district_of("경기도 성남시 분당구 성남대로 550 (수내동)"), "성남시 분당구")
        self.assertEqual(district_of("부산광역시 해운대구 해운대해변로 84"), "해운대구")
        self.assertEqual(district_of(""), "")


class TimelineTests(unittest.TestCase):
    def build(self, places, rest, used=None):
        from travel.schedule import build_timeline
        return build_timeline([{"place": p, "note": ""} for p in places], rest, used if used is not None else set())

    def test_lunch_dinner_and_chronological_order(self):
        a, b, c = P(1, "A", 37.380, 127.120), P(2, "B", 37.385, 127.125), P(3, "C", 37.390, 127.130)
        rest = [P(10, "식당1", 37.381, 127.121, "39"), P(11, "식당2", 37.391, 127.131, "39")]
        ev = self.build([a, b, c], rest)
        self.assertEqual(ev[0]["start"], "10:00")
        kinds = [e["kind"] for e in ev]
        self.assertEqual(kinds.count("meal"), 2)
        self.assertEqual([e["label"] for e in ev if e["kind"] == "meal"], ["점심", "저녁"])
        starts = [e["start"] for e in ev]
        self.assertEqual(starts, sorted(starts))                         # 시간 순서
        lunch = next(e for e in ev if e["kind"] == "meal")
        self.assertLessEqual(lunch["start"], "12:30")                    # 점심이 너무 늦지 않다
        for prev, nxt in zip(ev, ev[1:]):
            self.assertLessEqual(prev["end"], nxt["start"])              # 겹치지 않는다

    def test_meal_picks_nearest_unused_restaurant(self):
        a = P(1, "A", 37.380, 127.120)
        rest = [P(10, "먼식당", 37.450, 127.200, "39"), P(11, "가까운식당", 37.381, 127.121, "39")]
        used: set[str] = set()
        ev = self.build([a, P(2, "B", 37.382, 127.122)], rest, used)
        lunch = next(e for e in ev if e["kind"] == "meal")
        self.assertEqual(lunch["place"]["title"], "가까운식당")
        self.assertIn("11", used)

    def test_no_restaurants_still_gives_meal_slots_without_inventing_names(self):
        ev = self.build([P(1, "A", 37.38, 127.12), P(2, "B", 37.385, 127.125)], [])
        meals = [e for e in ev if e["kind"] == "meal"]
        self.assertTrue(meals)
        self.assertTrue(all(m["place"] is None for m in meals))

    def test_gap_before_dinner_becomes_free_time(self):
        ev = self.build([P(1, "A", 37.38, 127.12)], [P(10, "식당", 37.381, 127.121, "39")])
        self.assertTrue(any(e["kind"] == "free" for e in ev))  # 한 곳만 있으면 오후가 비므로 자유 시간으로 표시

    def test_empty_day_has_no_events(self):
        self.assertEqual(self.build([], [P(10, "식당", 37.38, 127.12, "39")]), [])

    def test_stay_duration_by_type(self):
        from travel.schedule import stay_minutes
        self.assertEqual(stay_minutes({"content_type_id": "28"}), 120)
        self.assertEqual(stay_minutes({"content_type_id": "38"}), 60)
        self.assertEqual(stay_minutes({}), 90)


class CleanTextTests(unittest.TestCase):
    def test_removes_candidate_ids(self):
        from travel.planner import clean_text
        self.assertEqual(clean_text("야외 공연장(C1)을 중심으로"), "야외 공연장을 중심으로")
        self.assertEqual(clean_text("C3 와 N2 를 확인"), "와 를 확인")
        self.assertEqual(clean_text("N서울타워 방문"), "N서울타워 방문")  # 숫자 없는 이름은 건드리지 않는다


class SigunguTests(unittest.TestCase):
    MAPPING = {"성남시 수정구": "131", "성남시 중원구": "133", "성남시 분당구": "135", "수원시 영통구": "117"}

    def test_resolve_city_with_districts_returns_all_codes(self):
        import travel.ldong as ld
        with patch("collectors.tourism.fetch_ldong_sigungu", return_value=self.MAPPING), \
             patch.object(ld, "resolve_ldong", return_value=("41", False)):
            got = ld.resolve_sigungu("경기", "성남")
            self.assertEqual({c for _, c in got}, {"131", "133", "135"})
            self.assertEqual([c for _, c in ld.resolve_sigungu("경기", "분당구")], ["135"])
            self.assertEqual(ld.resolve_sigungu("경기", "광안리"), [])  # 명소 이름은 시군구가 아님

    def test_resolve_failure_returns_empty(self):
        import travel.ldong as ld
        with patch("collectors.tourism.fetch_ldong_sigungu", side_effect=RuntimeError("api down")), \
             patch.object(ld, "resolve_ldong", return_value=("41", False)):
            self.assertEqual(ld.resolve_sigungu("경기", "성남"), [])

    def test_area_trip_fetches_whole_sigungu_in_one_call(self):
        """'성남'을 고르면 경기도 전체 60곳에서 거르는 대신 성남 시군구 전체를 받는다 (후보 1곳 문제의 수정)."""
        import travel.pipeline as pl
        calls = []

        def fake_info(**k):
            calls.append(k)
            return [dict(_place(str(i), f"성남장소{i}", ctype="관광지", addr="경기도 성남시 분당구 어딘가"),
                         content_type_id=("39" if i % 5 == 0 else "12")) for i in range(1, 41)]

        with patch.object(pl, "resolve_ldong", return_value=("41", False)), \
             patch.object(pl, "resolve_sigungu", return_value=[("성남시 분당구", "135")]), \
             patch.object(pl, "get_tourism_info", side_effect=fake_info), patch.object(pl, "get_festivals", return_value=[]):
            places, warns = pl._collect_candidates("경기", date(2026, 10, 7), date(2026, 10, 13), True, "성남")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["l_dong_signgu_cd"], "135")
        self.assertNotIn("content_type_id", calls[0])           # 유형 구분 없이 한 번에
        self.assertEqual(len(places), 40)                        # 1곳이 아니라 전부
        self.assertTrue(any(p["content_type_id"] == "39" for p in places))  # 음식점도 포함

    def test_landmark_area_falls_back_to_address_filter(self):
        import travel.pipeline as pl

        def fake_info(**k):
            return [dict(_place("1", "광안리해수욕장", addr="부산 수영구 광안해변로"), content_type_id="12"),
                    dict(_place("2", "다른곳", addr="부산 사하구"), content_type_id="12")] if k.get("content_type_id") == "12" else []

        with patch.object(pl, "resolve_ldong", return_value=("26", False)), patch.object(pl, "resolve_sigungu", return_value=[]), \
             patch.object(pl, "get_tourism_info", side_effect=fake_info), patch.object(pl, "get_festivals", return_value=[]):
            places, _ = pl._collect_candidates("부산", date(2026, 10, 7), date(2026, 10, 8), True, "광안리")
        self.assertEqual([p["title"] for p in places], ["광안리해수욕장"])


class NewsRelevanceTests(unittest.TestCase):
    def test_area_trip_requires_area_name_in_article(self):
        import travel.risk_scanner as rs
        from tests.test_chat import _news_item as _n  # noqa: F401
        from datetime import datetime, timedelta, timezone
        from email.utils import format_datetime

        def news(title, desc=""):
            return {"source": "naver_news", "title": title, "description": desc, "link": f"http://x/{title}",
                    "pub_date": format_datetime(datetime.now(timezone.utc) - timedelta(hours=3)), "raw": {}}

        def fake(query, display=10, sort="date"):
            return [news("성남 탄천 산책로 통제", "성남시 안전"), news("경기도 전역 폭설 특보"), news("강릉 중앙시장 사고")] if "통제" in query or "사고" in query else []

        with patch.object(rs, "search_news", side_effect=fake):
            items, _ = rs.scan_regional_risks("경기", area="성남")
        self.assertEqual([i["title"] for i in items], ["성남 탄천 산책로 통제"])


if __name__ == "__main__":
    unittest.main()
