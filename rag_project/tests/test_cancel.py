"""보낸 말 취소 (/chat/{id}/cancel): 대화 기억을 그 말을 보내기 전으로 되돌린다"""
import threading
import time
import unittest
from datetime import date
from unittest.mock import patch

import travel.chat as c
from tests.test_userplaces import FlowBase, HOTEL

TODAY = date(2026, 11, 9)


def fake_plan(session, *a, **k):
    session.plan = {"days": []}
    return "PLAN"


class CancelTests(unittest.TestCase):
    def setUp(self):
        for p in (patch.object(c, "_llm_extract", return_value=None),
                  patch.object(c, "_answer_list", return_value=("LIST", {}, []))):
            p.start()
            self.addCleanup(p.stop)

    def say(self, s, text):
        with patch.object(c, "_make_plan", side_effect=fake_plan):
            return c.handle_message(s, text, today=TODAY)

    def test_undo_just_finished_message(self):
        s = c.ChatSession()
        self.say(s, "부산 가고 싶어")
        before = (dict(s.slots), list(s.history))
        self.say(s, "내일부터 2박")
        self.assertEqual(s.slots["start_date"], "2026-11-10")
        self.assertEqual(c.cancel_turn(s), "undone")
        self.assertEqual((s.slots, s.history), before)
        self.assertEqual(c.cancel_turn(s), "pending")  # 되돌릴 말이 없으면 곧 올 말을 기다린다 (짧게)

    def test_old_message_is_not_undone(self):
        s = c.ChatSession()
        self.say(s, "부산 가고 싶어")
        s.undo = (s.undo[0], s.undo[1], time.time() - c.UNDO_WINDOW_SEC - 1)
        self.assertEqual(c.cancel_turn(s), "pending")
        self.assertEqual(s.slots["region"], "부산")

    def test_cancel_while_running_stops_before_llm_and_restores(self):
        s = c.ChatSession()
        for m in ("부산 내일부터", "2박"):  # 두 번째 답 뒤에 취향을 물어본다 → 다음 말에서 일정을 만든다
            self.say(s, m)
        started, release = threading.Event(), threading.Event()
        llm_called = []

        def slow_plan(session, *a, **k):
            started.set()
            release.wait(5)
            c.check_cancelled()  # AI를 부르기 직전
            llm_called.append(1)
            return "PLAN"

        out = {}
        before = (dict(s.slots), list(s.history))
        with patch.object(c, "_make_plan", side_effect=slow_plan):
            t = threading.Thread(target=lambda: out.update(r=c.handle_message(s, "실내 위주로 짜줘", today=TODAY)))
            t.start()
            self.assertTrue(started.wait(5))
            self.assertEqual(c.cancel_turn(s), "running")  # 처리 중이어도 기다리지 않고 바로 답한다
            release.set()
            t.join(5)
        self.assertEqual(llm_called, [])
        self.assertTrue(out["r"].get("cancelled"))
        self.assertEqual((s.slots, s.history), before)

    def test_cancel_arriving_before_message(self):
        s = c.ChatSession()
        self.assertEqual(c.cancel_turn(s), "pending")
        r = self.say(s, "부산 가고 싶어")
        self.assertTrue(r.get("cancelled"))
        self.assertFalse(s.slots["region"])
        r = self.say(s, "부산 가고 싶어")  # 다시 보낸 말은 처리된다
        self.assertFalse(r.get("cancelled"))
        self.assertEqual(s.slots["region"], "부산")

    def test_cancel_endpoint(self):
        from fastapi.testclient import TestClient
        import api_server
        client = TestClient(api_server.app)
        self.assertEqual(client.post("/chat/없는세션/cancel").json()["status"], "none")
        s = c.ChatSession()
        api_server.SESSIONS[s.session_id] = s
        self.addCleanup(api_server.SESSIONS.pop, s.session_id, None)
        self.say(s, "부산 가고 싶어")
        self.assertEqual(client.post(f"/chat/{s.session_id}/cancel").json()["status"], "undone")
        self.assertFalse(s.slots["region"])


class CancelRealFlowTests(FlowBase):
    """실제 일정 흐름(숙소·장소·축제)에서도 그 말이 바꾼 기억이 되돌려진다"""
    DB = {"스타호텔": [HOTEL]}

    def test_cancel_after_lodging_message_restores_the_state_before_it(self):
        self.make_plan()
        days_before = [list(d["items"]) for d in self.session.plan["days"]]
        history_before = len(self.session.history)
        self.say("숙소는 판교 스타호텔이야")
        self.assertIsNotNone(self.session.lodging)
        self.assertEqual(self.chat.cancel_turn(self.session), "undone")
        self.assertIsNone(self.session.lodging)                              # 숙소를 말하기 전으로
        self.assertEqual(len(self.session.history), history_before)           # 대화 기록에서도 사라진다
        self.assertEqual([d["items"] for d in self.session.plan["days"]], days_before)

    def test_cancelling_the_first_plan_request_returns_to_an_empty_conversation(self):
        self.say("전주 다음주 주말에 2박 3일 혼자 여행 일정 짜줘")
        self.assertIsNotNone(self.session.plan)
        self.assertEqual(self.chat.cancel_turn(self.session), "undone")
        self.assertIsNone(self.session.plan)
        self.assertEqual(self.session.slots["region"], "")
        self.assertEqual(self.session.history, [])

    def test_the_same_message_can_be_sent_again_after_cancel(self):
        first = self.say("전주 다음주 주말에 2박 3일 혼자 여행 일정 짜줘")
        self.chat.cancel_turn(self.session)
        again = self.say("전주 다음주 주말에 2박 3일 혼자 여행 일정 짜줘")
        self.assertEqual(first["reply"], again["reply"])


class ProgressTests(unittest.TestCase):
    """답을 기다리는 동안 지금 하는 일 (GET /chat/{id}/progress)"""

    def test_progress_while_running_and_cleared_after(self):
        s = c.ChatSession()
        seen, started, release = [], threading.Event(), threading.Event()

        def slow_plan(session, *a, **k):
            c.set_progress("AI가 일정을 짜고 있어요")
            started.set()
            release.wait(5)
            return "PLAN"

        with patch.object(c, "_llm_extract", return_value=None), patch.object(c, "_make_plan", side_effect=slow_plan):
            for m in ("부산 내일부터", "2박"):
                c.handle_message(s, m, today=TODAY)
            self.assertEqual(c.get_progress(s), {"busy": False, "step": "", "elapsed": 0})
            t = threading.Thread(target=lambda: c.handle_message(s, "실내 위주로", today=TODAY))
            t.start()
            self.assertTrue(started.wait(5))
            seen.append(c.get_progress(s))
            release.set()
            t.join(5)
        self.assertTrue(seen[0]["busy"])
        self.assertEqual(seen[0]["step"], "AI가 일정을 짜고 있어요")
        self.assertFalse(c.get_progress(s)["busy"])

    def test_progress_endpoint(self):
        from fastapi.testclient import TestClient
        import api_server
        r = TestClient(api_server.app).get("/chat/없는세션/progress").json()
        self.assertEqual((r["busy"], r["step"]), (False, ""))


if __name__ == "__main__":
    unittest.main()
