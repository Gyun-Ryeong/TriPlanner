"""연합뉴스 재난·사건사고 기사 (행정안전부 공유플랫폼) — 실제 API 없이 가짜 응답으로 확인"""
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import config
from collectors import yonhap
from travel import news, risk_scanner


def row(no, title, body, when):
    return {"YNA_NO": no, "YNA_TTL": title, "YNA_CN": body, "CRT_DT": when.strftime("%Y/%m/%d %H:%M:%S"),
            "YNA_REG_YMD": when.strftime("%Y-%m-%d"), "DEL_YN": "N"}


NOW = datetime.now()
ROWS = [
    row(101, "해운대 아파트서 불…주민 20명 대피",
        "해운대 아파트서 불…주민 20명 대피\n\n    (부산=연합뉴스) 홍길동 기자 = 오늘 오전 부산 해운대구 아파트에서 불이 났다.\n    hong@yna.co.kr\n(끝)\n",
        NOW - timedelta(days=1)),
    row(102, "국도서 차량 2대 충돌…3명 병원 이송",
        "국도서 차량 2대 충돌…3명 병원 이송\n\n    (서천=연합뉴스) 강수환 기자 = 충남 서천군 국도에서 차량 2대가 충돌했다.\n(끝)\n",
        NOW - timedelta(days=2)),
    row(104, "부산시설공단, 지반침하 대응 매뉴얼 제정…현장 통제 강화",
        "제목\n\n    (부산=연합뉴스) 기자 = 매뉴얼을 만들었다.\n", NOW - timedelta(days=1)),
    row(105, "[해수분해] 망망대해 선박 충돌사고…시시비비 누가 가리나",
        "제목\n\n    (부산=연합뉴스) 기자 = 해설.\n", NOW - timedelta(days=1)),
    row(103, "기장 해안도로 낙석으로 통제",
        "기장 해안도로 낙석으로 통제\n\n    (부산=연합뉴스) 김기자 기자 = 부산 기장군 해안도로가 낙석으로 통제됐다.\n(끝)\n",
        NOW - timedelta(days=1)),
]


def page(body, total=3):
    r = MagicMock()
    r.json.return_value = {"header": {"resultCode": "00"}, "totalCount": total, "body": body}
    return r


class YonhapCollectorTests(unittest.TestCase):
    def setUp(self):
        p = patch.object(config, "YONHAP_NEWS_API_KEY", "test-key")
        p.start()
        self.addCleanup(p.stop)

    def test_parses_articles_like_naver_news(self):
        with patch.object(yonhap.requests, "get", side_effect=[page([ROWS[0]]), page(ROWS)]):
            items = yonhap.recent_articles.__wrapped__()
        self.assertEqual([i["yna_no"] for i in items], [105, 104, 103, 102, 101])  # 최신(번호 큰) 순
        fire = items[-1]
        self.assertEqual(fire["dateline"], "부산")
        self.assertEqual(fire["link"], "")
        self.assertEqual(fire["source"], "연합뉴스")
        self.assertTrue(fire["description"].startswith("오늘 오전 부산 해운대구"))  # 제목·데이트라인·기자 이름 제외
        self.assertNotIn("@yna.co.kr", fire["description"])
        self.assertIn("+0900", fire["pub_date"])

    def test_deleted_articles_are_skipped(self):
        deleted = row(200, "<삭제>인천 구월동서 수도관 파열로 도로 침수", "본문", NOW)
        self.assertIsNone(yonhap._to_item(deleted))

    def test_unregistered_ip_is_explained(self):
        bad = MagicMock()
        bad.json.return_value = {"header": {"resultCode": "32", "errorMsg": "등록되지 않은 IP"}, "body": None}
        with patch.object(yonhap.requests, "get", return_value=bad):
            with self.assertRaises(yonhap.YonhapError) as e:
                yonhap.recent_articles.__wrapped__()
        self.assertIn("IP를 등록", str(e.exception))

    def test_region_match_uses_title_or_dateline(self):
        item = {"title": "국도서 차량 충돌", "dateline": "서천"}
        self.assertTrue(yonhap.matches_region(item, "서천"))
        self.assertFalse(yonhap.matches_region(item, "부산"))


class ColumnTests(unittest.TestCase):
    def test_columns_are_not_incident_news(self):
        self.assertTrue(news.is_column("[해수분해] 망망대해 선박 충돌사고…시시비비 누가 가리나"))
        self.assertTrue(news.is_column("[기자수첩] 안전 불감증"))
        self.assertFalse(news.is_column("[속보] 해운대 아파트서 불"))
        self.assertFalse(news.is_column("[단독] 부산 터널 통제"))
        self.assertFalse(news.is_column("해운대 아파트서 불"))


class YonhapInNewsTests(unittest.TestCase):
    def setUp(self):
        self.items = [yonhap._to_item(r) for r in ROWS]
        for p in (patch.object(config, "YONHAP_NEWS_API_KEY", "test-key"),
                  patch("collectors.yonhap.recent_articles", return_value=self.items)):
            p.start()
            self.addCleanup(p.stop)

    def test_safety_answer_includes_yonhap_by_dateline(self):
        with patch.object(news, "search_news", return_value=[]):
            reply, extra, warnings, _ = news.answer_safety("부산")
        self.assertIn("해운대 아파트서 불", reply)          # 제목에 '부산'이 없어도 데이트라인 (부산=연합뉴스) 로
        self.assertNotIn("국도서 차량", reply)             # 서천 기사는 제외
        self.assertIn("출처: 연합뉴스", reply)              # 링크가 없으니 출처로
        self.assertNotIn("]()", reply)
        self.assertNotIn("해수분해", reply)

    def test_yonhap_failure_keeps_naver(self):
        naver = [{"title": "부산 해운대서 화재 발생", "description": "불", "link": "https://n.news/1",
                  "pub_date": "Mon, 23 Nov 2026 10:00:00 +0900"}]
        with patch("collectors.yonhap.recent_articles", side_effect=RuntimeError("막힘")), \
             patch.object(news, "search_news", return_value=naver):
            reply, _, warnings, _ = news.answer_safety("부산")
        self.assertIn("기사 보기", reply)
        self.assertTrue(any("연합뉴스" in w for w in warnings))

    def test_no_key_skips_quietly(self):
        with patch.object(config, "YONHAP_NEWS_API_KEY", ""):
            self.assertEqual(news.fetch_yonhap(), ([], []))

    def test_regional_risks_include_yonhap_even_if_naver_down(self):
        with patch.object(risk_scanner, "search_news", side_effect=RuntimeError("naver down")):
            items, warnings = risk_scanner.scan_regional_risks("부산")
        titles = [i["title"] for i in items]
        self.assertIn("기장 해안도로 낙석으로 통제", titles)         # 통제·휴장 → 여행에 영향
        self.assertNotIn("해운대 아파트서 불…주민 20명 대피", titles)  # 여행 이슈 키워드(산불·침수·사고·통제…)가 없는 일반 화재는 제외
        self.assertFalse(any("매뉴얼" in t for t in titles))       # 대책·매뉴얼 같은 정책 기사 제외
        self.assertFalse(any("해수분해" in t for t in titles))     # 연재 해설 제외
        self.assertEqual(len(titles), len(set(titles)))
        self.assertTrue(all(i["source"] == "연합뉴스" for i in items))


if __name__ == "__main__":
    unittest.main()


class LinkAndBodyTests(unittest.TestCase):
    """원문 주소 찾기(네이버 검색) + 못 찾으면 화면에서 볼 본문"""

    def test_body_keeps_paragraphs(self):
        it = yonhap._to_item(row(301, "제목", "제목\n\n    (부산=연합뉴스) 홍길동 기자 = 첫 문단이다.\n    둘째 문단이다.\n    hong@yna.co.kr\n(끝)\n", NOW))
        self.assertEqual(it["body"], "첫 문단이다.\n둘째 문단이다.")

    def test_attach_links_finds_yna_article(self):
        found = [{"title": "부산 해운대 아파트서 불…주민 20명 대피", "link": "https://www.yna.co.kr/view/AKR1"},
                 {"title": "해운대 아파트 화재 대피", "link": "https://other.news/1"}]
        items = [{"title": "해운대 아파트서 불…주민 20명 대피", "source": "연합뉴스", "link": ""},
                 {"title": "전혀 다른 기사 제목입니다", "source": "연합뉴스", "link": ""},
                 {"title": "네이버 기사", "source": "", "link": "https://n/1"}]
        with patch("collectors.naver_news.search_news", return_value=found):  # 테스트는 캐시(API_CACHE)가 꺼져 있다
            yonhap.attach_links(items)
        self.assertEqual(items[0]["link"], "https://www.yna.co.kr/view/AKR1")  # yna.co.kr + 제목 비슷
        self.assertEqual(items[1]["link"], "")                                # 비슷한 제목이 없으면 그대로
        self.assertEqual(items[2]["link"], "https://n/1")                     # 링크 있는 기사는 건드리지 않음

    def test_attach_links_never_raises(self):
        items = [{"title": "제목", "source": "연합뉴스", "link": ""}]
        with patch.object(yonhap, "_find_link", side_effect=RuntimeError("네이버 키 없음")):
            yonhap.attach_links(items)
        self.assertEqual(items[0]["link"], "")
