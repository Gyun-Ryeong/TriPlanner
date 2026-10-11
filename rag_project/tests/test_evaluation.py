"""
일정 품질 지표 오프라인 테스트.

    python -m unittest tests.test_evaluation -v
"""
import unittest

from travel.evaluation import evaluate_plan
from travel.planner import normalize_plan


def _view(name, kind="관광지", indoor=False, x="129.16", y="35.16"):
    return {"name": name, "type": kind, "address": "", "indoor": indoor, "mapx": x, "mapy": y}


def _day(outdoor_ok, places):
    events = [{"kind": "visit", "place": p} for p in places]
    return {
        "outdoor_ok": outdoor_ok,
        "outdoor_count": sum(1 for p in places if not p["indoor"]),
        "events": events,
        "items": [{"place": p} for p in places],
    }


class NormalizeStatsTests(unittest.TestCase):
    def test_counts_proposed_and_dropped(self):
        cand = {"C1": {"title": "A"}, "C2": {"title": "B"}}
        parsed = {"message": "m", "days": [{"date": "2026-10-08", "items": [
            {"candidate_id": "C1"}, {"candidate_id": "C9"}, {"candidate_id": "C2"}, {"candidate_id": None, "note": "점심"},
        ]}]}
        stats = {}
        plan, _ = normalize_plan(parsed, cand, ["2026-10-08"], stats)
        self.assertEqual(stats, {"proposed": 3, "dropped": 1})  # 자유 문구(id 없음)는 장소 제안이 아니다
        self.assertEqual([i["candidate_id"] for i in plan["days"][0]["items"]], ["C1", "C2", None])


class EvaluatePlanTests(unittest.TestCase):
    def test_weather_fit_and_hallucination(self):
        days = [
            _day(False, [_view("박물관", "문화시설", True), _view("해변")]),  # 궂은 날: 실내 1 / 실외 1
            _day(True, [_view("공원")]),
        ]
        ev = evaluate_plan(days, {"proposed": 4, "dropped": 1}, "llm",
                           {"collect_sec": 3.0, "rank_sec": 0.5, "llm_sec": 20.0})
        self.assertEqual(ev["hallucination_rate"], 0.25)
        self.assertEqual(ev["bad_weather_days"], 1)
        self.assertEqual(ev["weather_fit_rate"], 0.5)
        self.assertEqual(ev["filled_day_rate"], 1.0)
        self.assertEqual(ev["avg_visits_per_day"], 1.5)
        self.assertEqual(ev["place_type_count"], 2)
        self.assertEqual(ev["response_sec"], 23.5)

    def test_no_bad_weather_and_fallback_have_no_rates(self):
        ev = evaluate_plan([_day(True, [_view("공원")])], {}, "fallback")
        self.assertIsNone(ev["weather_fit_rate"])  # 궂은 날이 없으면 판단 대상이 아니다
        self.assertIsNone(ev["hallucination_rate"])  # 기본 일정은 AI가 장소를 고르지 않았다
        self.assertIsNone(ev["response_sec"])

    def test_daily_distance_skips_missing_coordinates(self):
        a = _view("A", x="126.9770", y="37.5788")  # 경복궁 부근
        b = _view("B", x="126.9910", y="37.5704")  # 약 1.5km
        c = _view("C", x="", y="")  # 좌표 없음
        ev = evaluate_plan([_day(True, [a, c, b])], {"proposed": 3, "dropped": 0}, "llm")
        self.assertEqual(ev["daily_distance_km"], [0.0])  # A-C, C-B 모두 좌표가 없어 건너뛴다
        ev = evaluate_plan([_day(True, [a, b])], {"proposed": 2, "dropped": 0}, "llm")
        self.assertAlmostEqual(ev["daily_distance_km"][0], 1.5, delta=0.2)


class ChatEvaluationTests(unittest.TestCase):
    """실제 대화 흐름에서 지표가 일정 응답에만, 개발자 모드일 때만 실리는지."""

    def setUp(self):
        from tests.test_chat import ChatFlowTests
        self.flow = ChatFlowTests("test_plan_reflects_weather_and_dust_in_reply")
        self.flow.setUp()
        self.addCleanup(self.flow.doCleanups)
        self.flow.llm_plan = self.flow.plan_response()

    def say(self, text, debug):
        f = self.flow
        return f.chat.handle_message(f.session, text, today=__import__("tests.test_chat").test_chat.TODAY,
                                     ranker=f.ranker, debug=debug)

    def test_metrics_only_on_plan_reply_in_dev_mode(self):
        from unittest.mock import patch
        with patch.object(self.flow.chat, "DEV_MODE", False):
            self.say("이번 주말 부산 갈래", True)
            r = self.say("상관없어요", True)
            ev = r["evaluation"]
            self.assertEqual(ev["source"], "llm")
            self.assertEqual(ev["hallucination_rate"], 0.0)
            self.assertEqual(ev["bad_weather_days"], 2)  # 테스트 데이터는 이틀 모두 궂은 날
            self.assertIsNotNone(ev["weather_fit_rate"])
            # 일정을 다시 만들지 않는 다음 응답에는 이전 지표가 다시 실리지 않는다
            r = self.say("개발자 정보 알려줘", True)
            self.assertEqual(r["intent"], "about")
            self.assertIsNone(r["evaluation"])

    def test_hidden_without_dev_mode(self):
        from unittest.mock import patch
        with patch.object(self.flow.chat, "DEV_MODE", False):
            self.say("이번 주말 부산 갈래", False)
            self.assertIsNone(self.say("상관없어요", False)["evaluation"])


if __name__ == "__main__":
    unittest.main()
