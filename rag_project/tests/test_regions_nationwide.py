"""
전국 시·군·구 어디로든 일정을 짤 수 있는지 (도만 말해도, 시·군·구까지 말해도) 확인하는 오프라인 테스트.

    python -m unittest tests.test_regions_nationwide -v
"""
import tempfile
import unittest
from datetime import date
from unittest.mock import patch

TODAY = date(2026, 10, 6)

# ldongCode2 응답 흉내. 광주·전남은 실제처럼 한 코드("12")를 함께 쓴다
CODES = {"광주": ("12", True), "전남": ("12", True)}
SIG = {
    "12": {"목포시": "1", "곡성군": "2", "진도군": "3", "동구": "4", "광산구": "5"},
    "강원": {"고성군": "1", "춘천시": "2"}, "경남": {"고성군": "1", "창원시 성산구": "2"},
    "경기": {"광명시": "1", "광주시": "2", "성남시 분당구": "3", "고양시 덕양구": "4"},
    "부산": {"중구": "1", "서구": "2", "강서구": "3"}, "대구": {"중구": "1"}, "서울": {"강서구": "1"},
}


class NationwideRegionTests(unittest.TestCase):
    def setUp(self):
        import travel.gazetteer as gz
        import travel.chat as chat
        self.gz, self.chat = gz, chat
        gz.reset_for_tests()
        self.addCleanup(gz.reset_for_tests)
        for p in [patch("travel.ldong.resolve_ldong", side_effect=lambda s: CODES.get(s, (s, False))),
                  patch("collectors.tourism.fetch_ldong_sigungu", side_effect=lambda code: SIG.get(code, {})),
                  patch.object(gz.config, "GAZETTEER_CACHE_PATH", tempfile.mkdtemp() + "/gz.json")]:
            p.start()
            self.addCleanup(p.stop)

    def test_shared_code_is_split_between_metro_and_province(self):
        self.assertEqual(self.gz.lookup_regions("곡성 여행"), [("전남", "곡성")])
        self.assertEqual(self.gz.lookup_regions("진도 1박2일"), [("전남", "진도")])
        self.assertEqual(self.gz.lookup_regions("광산구 맛집"), [("광주", "광산")])

    def test_province_or_city_both_resolve(self):
        r = self.chat.resolve_place_ext
        self.assertEqual(r("경기도 2박3일"), ("경기", ""))
        self.assertEqual(r("성남시 2박3일"), ("경기", "성남"))
        self.assertEqual(r("곡성 1박2일"), ("전남", "곡성"))

    def test_same_name_in_several_sido_needs_the_sido(self):
        r = self.chat.resolve_place_ext
        self.assertEqual(r("고성 1박2일"), (None, ""))
        self.assertEqual(r("강원 고성 1박2일"), ("강원", "고성"))
        self.assertEqual(r("부산 중구 일정"), ("부산", "중구"))
        self.assertEqual(r("경기 광주 1박2일"), ("경기", "광주"))   # 광역시 광주가 아니라 경기 광주시
        self.assertEqual(r("광주 동구 일정"), ("광주", "동구"))
        self.assertEqual(self.gz.ambiguous_regions("고성 1박2일"), [("고성", ["강원", "경남"])])

    def test_everyday_words_need_trip_context(self):
        r = self.chat.resolve_place_ext
        self.assertEqual(r("광명 1박2일"), ("경기", "광명"))
        self.assertEqual(r("고양 일정 짜줘"), ("경기", "고양"))
        self.assertEqual(r("고양이랑 갈래"), (None, ""))
        self.assertEqual(r("광명 찾았다"), (None, ""))

    def test_ambiguous_name_is_asked_and_short_answer_is_understood(self):
        chat = self.chat
        s = chat.ChatSession()
        with patch.object(chat, "chat_json_messages", side_effect=RuntimeError("ollama down")):
            r = chat.handle_message(s, "고성 10월 10일부터 1박2일", today=TODAY)
            self.assertIn("강원, 경남", r["reply"])
            self.assertNotIn("어느 지역으로 가실 건가요", r["reply"])  # 같은 걸 두 번 묻지 않는다
            self.assertEqual(r["slots"]["region"], "")
            r = chat.handle_message(s, "강원", today=TODAY)
        self.assertEqual((r["slots"]["region"], r["slots"]["area"]), ("강원", "고성"))
        self.assertEqual(r["slots"]["start_date"], "2026-10-10")  # 앞에서 말한 날짜는 그대로

    def test_sigungu_match_does_not_catch_longer_names(self):
        from travel.ldong import resolve_sigungu
        with patch("travel.ldong.resolve_ldong", side_effect=lambda s: (s, False)):
            self.assertEqual(resolve_sigungu("부산", "서구"), [("서구", "2")])   # 강서구는 빼고
            self.assertEqual(resolve_sigungu("경기", "분당"), [("성남시 분당구", "3")])


if __name__ == "__main__":
    unittest.main()
