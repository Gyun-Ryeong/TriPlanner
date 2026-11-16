"""회원 취향 기억: 저장한 여행 장소로 취향 짐작, 다녀온 곳은 뒤로"""
import unittest
from datetime import date
from unittest.mock import patch

import travel.chat as c
from travel.profile import push_visited_back, taste_words

TODAY = date(2026, 11, 9)
MUSEUM_LOVER = {"categories": {"문화시설": 6, "관광지": 3, "음식점": 3},
                "place_names": ["국립중앙박물관", "부산박물관", "카페 오션", "카페 해변", "해운대해수욕장", "경주박물관"],
                "visited_ids": ["111"], "regions": ["부산 해운대구"]}


class TasteTests(unittest.TestCase):
    def test_taste_words(self):
        self.assertEqual(taste_words(MUSEUM_LOVER), ["박물관", "카페", "미술관"])

    def test_not_enough_data(self):
        self.assertEqual(taste_words({"categories": {"문화시설": 2}, "place_names": ["A박물관", "B박물관"]}), [])
        self.assertEqual(taste_words(None), [])
        self.assertEqual(taste_words({}), [])

    def test_common_types_are_not_taste(self):
        prof = {"categories": {"관광지": 10, "음식점": 8}, "place_names": [f"장소{i}" for i in range(10)]}
        self.assertEqual(taste_words(prof), [])

    def test_visited_go_last(self):
        places = [{"content_id": "111", "title": "다녀온 곳"}, {"content_id": "222", "title": "새 곳"}]
        self.assertEqual([p["title"] for p in push_visited_back(places, MUSEUM_LOVER)], ["새 곳", "다녀온 곳"])
        self.assertEqual(push_visited_back(places, None), places)


class ChatProfileTests(unittest.TestCase):
    """실제 대화 흐름(가짜 API·AI)에서 취향 요약이 장소 고르기와 답변에 반영되는지"""
    from tests.test_chat import ChatFlowTests as _Flow
    PLACES = _Flow.PLACES
    setUp = _Flow.setUp
    say = _Flow.say
    plan_response = _Flow.plan_response

    def capture_queries(self):
        seen, real = [], c.rank_places

        def spy(places, sido, query, ranker=None):
            seen.append(query)
            return real(places, sido, query, ranker)

        p = patch.object(c, "rank_places", side_effect=spy)
        p.start()
        self.addCleanup(p.stop)
        return seen

    def test_taste_used_when_no_preference_stated(self):
        seen = self.capture_queries()
        self.session.profile = MUSEUM_LOVER
        self.llm_plan = self.plan_response()
        self.say("이번 주말 부산 갈래")
        r = self.say("상관없어요")
        self.assertIn("박물관", seen[0])
        self.assertIn("💡 지난 여행에서 자주 담으신 박물관·카페·미술관 취향을 반영했어요", r["reply"])

    def test_stated_preference_wins(self):
        seen = self.capture_queries()
        self.session.profile = MUSEUM_LOVER
        self.llm_plan = self.plan_response()
        self.say("이번 주말 부산 갈래")
        self.llm_extract = {"preferences": "바다 산책"}  # 이 테스트 환경은 취향을 AI 추출로 읽는다
        r = self.say("바다 산책 위주로")
        self.assertNotIn("박물관", seen[0])
        self.assertNotIn("지난 여행에서", r["reply"])

    def test_no_profile_no_note(self):
        self.llm_plan = self.plan_response()
        self.say("이번 주말 부산 갈래")
        self.assertNotIn("지난 여행에서", self.say("상관없어요")["reply"])

    def test_api_passes_profile_to_session(self):
        from fastapi.testclient import TestClient
        import api_server
        client = TestClient(api_server.app)
        with patch.object(api_server, "handle_message", side_effect=lambda sess, *a, **k: {"session_id": sess.session_id}):
            sid = client.post("/chat", json={"message": "", "profile": MUSEUM_LOVER}).json()["session_id"]
        self.addCleanup(api_server.SESSIONS.pop, sid, None)
        self.assertEqual(api_server.SESSIONS[sid].profile["visited_ids"], ["111"])


if __name__ == "__main__":
    unittest.main()
