"""지역 뉴스 질문(Case A 포괄 / Case B 특정 대상) 오프라인 테스트."""
import unittest
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from unittest.mock import patch

from tests.test_offline import FakeRanker

TODAY = __import__("datetime").date(2026, 10, 6)


def news(title, desc="", days_ago=1, link=None):
    dt = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return {"source": "naver_news", "title": title, "description": desc, "link": link or f"http://news/{abs(hash(title))}",
            "pub_date": format_datetime(dt), "raw": {}}


class ParseTests(unittest.TestCase):
    def test_broad_vs_targeted(self):
        from travel.news import parse_news_request as p
        self.assertEqual(p("성남시 요즘 소식 있어?")["target"], "")
        self.assertEqual(p("최근 성남 이슈 알려줘")["target"], "")
        self.assertEqual(p("성남 야외공연장 뉴스 알려줘")["target"], "야외공연장")
        self.assertEqual(p("모란시장 관련 소식 알려줘")["target"], "모란시장")
        self.assertEqual(p("성남 중앙공원에 대한 뉴스")["target"], "중앙공원")

    def test_region_inside_a_word_is_not_a_region(self):
        from travel.news import parse_news_request as p
        r = p("분당 서울대병원 소식")
        self.assertEqual((r["sido"], r["area"], r["target"]), ("경기", "분당", "서울대병원"))  # '서울'을 지역으로 오인하지 않는다

    def test_region_resolution(self):
        from travel.news import parse_news_request as p
        self.assertEqual((p("성남시 소식")["sido"], p("성남시 소식")["area"]), ("경기", "성남"))
        self.assertEqual((p("부산 소식")["sido"], p("부산 소식")["area"]), ("부산", ""))
        self.assertIsNone(p("모란시장 소식")["sido"])


class BroadTests(unittest.TestCase):
    def test_picks_3_to_4_recent_relevant_unique_items(self):
        from travel.news import pick_broad
        items = [
            news("성남시, 탄천 가을 축제 개최", "성남시는 이번 주말 탄천에서 축제를 연다", 1),
            news("성남시 탄천 가을축제 이번 주말 열려", "성남 탄천에서 가을 축제가 열린다", 1),       # 같은 사건 (중복)
            news("성남시, 버스 노선 개편 발표", "성남시가 버스 노선을 개편한다", 2),
            news("성남시의회 임시회 개회", "성남시의회가 임시회를 연다", 3),
            news("분당 신축 아파트 분양 시작", "성남 분당구에서 분양이 시작된다", 4),
            news("부산 해운대 불꽃축제 개최", "부산에서 열린다", 1),                                # 다른 지역
            news("성남시, 작년 행사 결산", "성남시 과거 소식", 40),                                  # 너무 오래됨
            news("서울 지하철 파업", "서울 소식", 1),
            news("경기도 전역 폭우", "성남을 포함한 경기도", 1),
        ]
        out = pick_broad(items, "성남")
        titles = [i["title"] for i in out]
        self.assertTrue(3 <= len(out) <= 4, titles)
        self.assertEqual(len([t for t in titles if "탄천" in t]), 1)           # 같은 사건은 하나
        self.assertFalse(any("부산" in t or "서울" in t for t in titles))       # 다른 지역 제외
        self.assertNotIn("성남시, 작년 행사 결산", titles)                       # 오래된 기사 제외
        self.assertEqual(titles[0], "성남시, 탄천 가을 축제 개최")               # 제목에 지역이 있는 최신 기사 먼저

    def test_render_has_no_greeting_and_includes_links(self):
        from travel.news import render_broad
        text, views = render_broad("성남", [news("성남시 소식1", "설명1", 1, "http://a"), news("성남시 소식2", "설명2", 2, "http://b")])
        self.assertTrue(text.startswith("## 성남 최근 소식"))
        self.assertIn("[기사 보기](http://a)", text)
        self.assertEqual(len(views), 2)


class FocusTests(unittest.TestCase):
    ITEMS = [
        news("성남 야외공연장서 가을 음악회 열려", "성남시 야외공연장에서 이번 주말 음악회가 열린다", 2, "http://hit"),
        news("성남 야외공연장 보수 공사 시작", "성남시가 야외공연장 보수에 들어간다", 10, "http://older"),
        news("성남시 버스 노선 개편", "성남시 소식", 1),
        news("서울 야외공연장 개장", "서울시 소식", 1),                       # 다른 지역의 같은 시설
        news("성남 모란시장 5일장 활기", "모란시장 소식", 1),
    ]

    def test_returns_exactly_one_directly_related_article(self):
        from travel.news import pick_focus
        it = pick_focus(self.ITEMS, "야외공연장", "성남")
        self.assertEqual(it["link"], "http://hit")                              # 대상과 직접 관련된 가장 최근 기사
        self.assertIsInstance(it, dict)

    def test_other_region_same_facility_is_excluded(self):
        from travel.news import pick_focus
        self.assertNotEqual(pick_focus(self.ITEMS, "야외공연장", "성남")["title"], "서울 야외공연장 개장")

    def test_spacing_differences_still_match(self):
        from travel.news import pick_focus
        items = [news("성남 야외 공연장 개장", "소식", 1, "http://x")]
        self.assertEqual(pick_focus(items, "야외공연장", "성남")["link"], "http://x")

    def test_none_when_unrelated(self):
        from travel.news import pick_focus
        self.assertIsNone(pick_focus(self.ITEMS, "남한산성", "성남"))

    def test_render_focus_shows_one_item_and_natural_message_when_none(self):
        from travel.news import pick_focus, render_focus
        text, views = render_focus("야외공연장", pick_focus(self.ITEMS, "야외공연장", "성남"))
        self.assertEqual(len(views), 1)
        self.assertEqual(text.count("[기사 보기]"), 1)
        none_text, none_views = render_focus("남한산성", None)
        self.assertEqual(none_views, [])
        self.assertIn("'남한산성'과 직접 관련된 최근 소식은 찾지 못했어요", none_text)   # 받침 있는 말은 '과'
        self.assertIn("'모란시장'과", render_focus("모란시장", None)[0])
        self.assertIn("'공연'과", render_focus("공연", None)[0])
        self.assertIn("'버스'와", render_focus("버스", None)[0])                          # 받침 없는 말은 '와' 


class ChatNewsTests(unittest.TestCase):
    def setUp(self):
        import travel.chat as chat
        self.chat = chat
        self.session = chat.ChatSession()
        self.queries = []
        self.corpus = FocusTests.ITEMS + [news("성남시, 탄천 가을 축제 개최", "성남시 소식", 1), news("성남시의회 임시회", "성남시의회", 2),
                                         news("성남시 청년 지원금 접수", "성남시 소식", 3)]

        def fake_search(query, display=10, sort="date"):
            self.queries.append(query)
            return list(self.corpus)

        self.patches = [patch("travel.news.search_news", side_effect=fake_search),
                        patch.object(chat, "chat_json_messages", side_effect=AssertionError("뉴스 질문은 AI 호출이 필요 없다"))]
        for p in self.patches:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in self.patches])

    def say(self, text):
        return self.chat.handle_message(self.session, text, today=TODAY, ranker=FakeRanker())

    def test_intent_detection(self):
        d = lambda t: self.chat.detect_intent(t, self.chat.ChatSession())
        self.assertEqual(d("성남시 요즘 소식 있어?"), "news")
        self.assertEqual(d("모란시장 관련 소식 알려줘"), "news")
        self.assertEqual(d("성남 7일 일정 짜줘"), "plan")
        self.assertEqual(d("분당 맛집 알려줘"), "food")

    def test_modifying_a_plan_with_the_word_news_stays_a_plan_request(self):
        s = self.chat.ChatSession()
        s.plan = {"days": []}
        self.assertEqual(self.chat.detect_intent("뉴스에 나온 곳은 빼줘", s), "plan")

    def test_case_a_gives_a_short_list(self):
        r = self.say("성남시 요즘 소식 있어?")
        self.assertEqual(r["intent"], "news")
        self.assertTrue(3 <= len(r["news"]) <= 4, [n["title"] for n in r["news"]])
        self.assertTrue(r["reply"].startswith("## 성남 최근 소식"))
        self.assertFalse(any("부산" in n["title"] or "서울" in n["title"] for n in r["news"]))

    def test_case_b_gives_a_single_focused_article(self):
        r = self.say("성남 야외공연장 뉴스 알려줘")
        self.assertEqual(len(r["news"]), 1)
        self.assertIn("야외공연장", r["news"][0]["title"])
        self.assertNotIn("버스 노선", r["reply"])                     # 무관한 기사는 나열하지 않는다
        self.assertEqual(r["reply"].count("[기사 보기]"), 1)
        self.assertIn("성남 야외공연장", self.queries[0])             # 지역+대상으로 검색

    def test_case_b_without_region_still_works(self):
        r = self.say("모란시장 관련 소식 알려줘")
        self.assertEqual(len(r["news"]), 1)
        self.assertIn("모란시장", r["news"][0]["title"])

    def test_broad_without_region_asks_which_region_but_not_dates(self):
        r = self.say("요즘 소식 있어?")
        self.assertIn("어느 지역", r["reply"])
        self.assertNotIn("언제", r["reply"])

    def test_session_region_is_used_for_broad_question(self):
        self.session.slots.update(region="경기", area="성남")
        r = self.say("요즘 소식 알려줘")
        self.assertTrue(r["news"])

    def test_api_failure_gives_natural_message_and_details_only_in_dev_info(self):
        with patch("travel.news.search_news", side_effect=RuntimeError("401 bad key")):
            r = self.say("성남시 요즘 소식 있어?")
        for bad in ("RuntimeError", "401", "Error", "⚠️", "실패"):
            self.assertNotIn(bad, r["reply"])
        self.assertIn("불러오지 못했어요", r["reply"])
        self.assertTrue(any("401" in c for c in r["caveats"]))          # 개발자 정보에는 사유가 남는다

    def test_news_question_does_not_disturb_an_existing_plan(self):
        self.session.plan = {"days": [{"theme": "", "items": []}]}
        self.session.slots.update(region="부산", start_date="2026-10-10", end_date="2026-10-11")
        r = self.say("성남 야외공연장 뉴스 알려줘")
        self.assertEqual(self.session.slots["region"], "부산")
        self.assertIsNotNone(self.session.plan)
        self.assertEqual(r["stage"], "planned")


class RecommendWithFoodTests(unittest.TestCase):
    def test_general_recommendation_includes_a_food_category_but_sights_only_does_not(self):
        from tests.test_chat import ListAnswerTests
        t = ListAnswerTests("test_recommend_groups_by_theme_with_address_and_feature_and_no_dates_asked")
        t.setUp()
        try:
            general = t.say("성남 가볼 만한 곳 추천해줘")
            self.assertIn("🍽 맛집·카페", general["reply"])
            food_names = [p["name"] for p in general["places"] if p["category"] == "🍽 맛집·카페"]
            self.assertTrue(1 <= len(food_names) <= 3, food_names)
            self.assertIn("분당 한우마을", food_names)                 # 메뉴·영업 정보가 있는 곳 우선
            self.assertIn("💡 한우 갈비탕", general["reply"])         # 맛집 특징은 대표 메뉴
            only = t.say("성남 여행지만 추천해줘")
            self.assertNotIn("🍽", only["reply"])
        finally:
            t.doCleanups()


if __name__ == "__main__":
    unittest.main()
