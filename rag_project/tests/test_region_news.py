"""여행지 소식 카드: 기사 대표 사진 찾기, 이슈 판별, 카드 조립 (네트워크 없이)"""
import unittest
from unittest.mock import patch

from collectors import og_image as og
from travel import region_news as rn


class OgImageTests(unittest.TestCase):
    def test_parse_og_image(self):
        page = ('<html><head><meta name="twitter:image" content="https://img.example/tw.jpg">'
                '<meta content="/photos/a.jpg?w=1&amp;h=2" property="og:image"></head>')
        self.assertEqual(og.parse_og_image(page, "https://news.example/article/1"),
                         "https://news.example/photos/a.jpg?w=1&h=2")  # og:image 우선, 상대 주소·&amp; 처리

    def test_falls_back_to_twitter_and_empty(self):
        self.assertEqual(og.parse_og_image("<meta name='twitter:image' content='https://i.example/t.png'>", "https://a"),
                         "https://i.example/t.png")
        self.assertEqual(og.parse_og_image("<head><title>x</title></head>", "https://a"), "")

    def test_internal_addresses_are_not_opened(self):
        self.assertFalse(og._public_host("http://localhost:8080/admin"))
        self.assertFalse(og._public_host("http://127.0.0.1/x"))
        self.assertFalse(og._public_host("http://192.168.0.10/x"))
        self.assertFalse(og._public_host("file:///etc/passwd"))
        self.assertEqual(og.og_image(""), "")


class IssueFilterTests(unittest.TestCase):
    def test_travel_issue(self):
        self.assertTrue(rn.is_travel_issue("'삼각봉 14.5㎝ 눈' 한라산 탐방 통제…곳곳 강풍 피해도(종합)"))
        self.assertTrue(rn.is_travel_issue("인천 구월동서 수도관 파열로 도로 침수…\"복구 중\""))
        self.assertFalse(rn.is_travel_issue("점검부터 사고 수리까지 한 번에⋯ 포드·링컨, 부산 통합 서비스센터"))  # 광고
        self.assertFalse(rn.is_travel_issue("교통사고 수습 돕던 시민 치어 숨지게 한 60대, 2심도 금고형"))     # 재판
        self.assertFalse(rn.is_travel_issue("해수부, 겨울철 선원 안전사고 예방 당부"))                         # 예방
        self.assertFalse(rn.is_travel_issue("중부해경청 회전익정비대, 창설 25년간 무사고"))                     # 무사고
        self.assertFalse(rn.is_travel_issue("부산 롯데월드 겨울 축제 개막"))                                   # 이슈 단어 없음


INCIDENTS = [{"title": "부산 서면 상가 화재…10명 대피", "description": "불", "link": "https://n.example/f",
              "pub_date": "Mon, 23 Nov 2026 08:00:00 +0900"},
             {"title": "해운대 해수욕장 일대 통제 중 사고", "description": "같은 사건", "link": "https://n.example/x",
              "pub_date": "Mon, 23 Nov 2026 07:00:00 +0900"}]


class AssembleTests(unittest.TestCase):
    def test_cards_issues_first_photos_and_fallback(self):
        risks = [{"category": "통제·휴장", "title": "해운대 해수욕장 일대 통제", "description": "통제 중", "link": "",
                  "source": "연합뉴스", "pub_date": "2026-11-23 10:00"},
                 {"category": "통제·휴장", "title": "해운대 해수욕장 일대 통제…주말까지", "description": "같은 사건",
                  "link": "https://n.example/2", "source": "", "pub_date": "2026-11-23 09:00"}]
        broad = [{"title": "부산 국비 요청", "description": "예산", "link": "https://n.example/b",
                  "pub_date": "Mon, 23 Nov 2026 10:00:00 +0900"},
                 {"title": "롯데월드 부산 겨울 축제 개막", "description": "축제", "link": "https://n.example/a",
                  "pub_date": "Mon, 23 Nov 2026 09:00:00 +0900"}]
        images = {"https://n.example/a": "https://img/a.jpg", "https://n.example/b": ""}
        with patch.object(rn, "scan_regional_risks", return_value=(risks, [])), \
             patch.object(rn.news, "fetch", return_value=(broad, [])), \
             patch.object(rn.news, "pick_broad", side_effect=lambda items, label, n: items), \
             patch.object(rn.news, "fetch_yonhap", return_value=([], [])), \
             patch.object(rn.news, "pick_safety", return_value=INCIDENTS), \
             patch.object(rn, "attach_links", return_value=None), \
             patch.object(rn, "og_image", side_effect=lambda url: images.get(url, "")), \
             patch.object(rn, "region_photo", return_value={"image": "https://img/region.jpg"}):
            out = rn.region_news("부산", "경상도")
        incident = [(c["kind"], c["title"], c["category"]) for c in out["items"] if c["group"] == "incident"]
        local = [c["title"] for c in out["items"] if c["group"] == "local"]
        self.assertEqual(incident[0][:2], ("issue", "해운대 해수욕장 일대 통제"))  # 사건사고 칸: 여행 영향 이슈 먼저
        self.assertEqual(sum(k == "issue" for k, _, _ in incident), 1)         # 같은 사건 이슈는 하나로
        self.assertIn(("incident", "부산 서면 상가 화재…10명 대피", "화재"), incident)
        self.assertEqual(len(incident), 2)                                    # 이슈와 같은 사고 기사는 하나로
        self.assertEqual(local[0], "롯데월드 부산 겨울 축제 개막")               # 지역 소식 칸: 여행 관련 먼저
        self.assertEqual(out["counts"], {"incident": 2, "local": 2, "issue": 1})
        by_title = {c["title"]: c for c in out["items"]}
        self.assertEqual(by_title["롯데월드 부산 겨울 축제 개막"]["image"], "https://img/a.jpg")
        self.assertFalse(by_title["롯데월드 부산 겨울 축제 개막"]["image_is_fallback"])
        self.assertEqual(by_title["해운대 해수욕장 일대 통제"]["image"], "https://img/region.jpg")  # 링크 없는 기사 → 지역 사진
        self.assertTrue(by_title["해운대 해수욕장 일대 통제"]["image_is_fallback"])
        self.assertEqual(by_title["부산 국비 요청"]["date"], "2026-11-23")
        issue = by_title["해운대 해수욕장 일대 통제"]                       # 연합뉴스·원문 못 찾음 → 본문 보기
        self.assertEqual(issue["body"], "통제 중")
        self.assertIn("공유플랫폼", issue["credit"])
        self.assertNotIn("body", by_title["롯데월드 부산 겨울 축제 개막"])      # 원문 링크가 있으면 본문은 싣지 않음

    def test_unknown_region(self):
        with patch.object(rn, "_resolve", return_value=(None, "")):
            out = rn.region_news("없는곳")
        self.assertEqual(out["items"], [])


if __name__ == "__main__":
    unittest.main()
