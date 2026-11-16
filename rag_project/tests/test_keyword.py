"""키워드 검색 + 벡터 검색 섞기 (하이브리드)"""
import unittest

from tests.test_offline import _place
from travel.context import rank_places
from travel.keyword import expand_rare, fuse, keyword_score, query_terms


class ReverseRanker:
    """키워드와 반대로 줄 세우는 가짜 벡터 순위 (키워드가 순위를 끌어올리는지 보려고)"""

    def rank(self, items, query):
        return [k for k, _ in reversed(items)]


class KeywordTests(unittest.TestCase):
    def test_query_terms(self):
        self.assertEqual(query_terms("대구 국밥 맛집 위주로", ("대구",)), ["국밥"])
        self.assertEqual(query_terms("아이랑 갈 실내 박물관", ()), ["실내", "박물관"])
        self.assertEqual(query_terms("전주 한옥마을 산책", ("전북",)), ["전주", "한옥마을", "산책"])
        self.assertEqual(query_terms("국밥집 가고 싶어", ()), ["국밥"])
        self.assertEqual(query_terms("등산하기 좋은 산", ()), ["등산", "산"])
        self.assertEqual(query_terms("부산 해운대구 2박 3일", ("부산",)), ["해운대구"])

    def test_keyword_score(self):
        p = {"title": "청도돼지국밥"}
        self.assertEqual(keyword_score(p, ["국밥"]), 3)
        self.assertEqual(keyword_score({"title": "봉포"}, ["해수욕장"], category="해변>해수욕장"), 2)
        self.assertEqual(keyword_score({"title": "무명"}, ["야경"], overview="야경이 아름다운 곳"), 1)
        self.assertEqual(keyword_score({"title": "카페"}, ["국밥"]), 0)

    def test_rare_compound_also_matches_its_tail(self):
        texts = ["부전시장", "초량시장", "해운대해수욕장"] + ["해수욕장"] * 5
        self.assertEqual(expand_rare(["전통시장"], texts), ["전통시장", ("시장", 0.5)])
        self.assertEqual(expand_rare(["해수욕장"], texts), ["해수욕장"])  # 통째로 많이 맞으면 그대로
        self.assertEqual(keyword_score({"title": "부전시장"}, [("시장", 0.5)]), 1.5)

    def test_fuse_keeps_vector_order_without_hits(self):
        self.assertEqual(fuse(["a", "b", "c"], {}), ["a", "b", "c"])
        self.assertEqual(fuse(["a", "b", "c"], {"c": 3})[0], "c")

    def test_rank_places_lifts_exact_word(self):
        places = [_place("1", "국일따로국밥", addr="대구 중구"), _place("2", "룰리커피", addr="대구 수성구"),
                  _place("3", "원주통닭", addr="대구 북구")]
        out = rank_places(places, "대구", "대구 국밥 맛집", ReverseRanker())
        self.assertEqual(out[0]["title"], "국일따로국밥")  # 벡터로는 꼴찌였지만 '국밥'이 이름에 있어 1등

    def test_region_word_in_all_addresses_is_not_a_keyword(self):
        # '해운대'는 후보 모두의 주소에 있으니 지역 이름 → 이름에 '해운대'가 있다고 끌어올리지 않는다
        places = [_place("1", "해운대 횟집", addr="부산 해운대구 우동"), _place("2", "동백섬", addr="부산 해운대구 중동")]
        out = rank_places(places, "부산", "부산 해운대 여행", ReverseRanker())
        self.assertEqual([p["title"] for p in out], ["동백섬", "해운대 횟집"])


if __name__ == "__main__":
    unittest.main()
