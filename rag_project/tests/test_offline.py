"""
API 키, Ollama, 인터넷 없이 로직만 검증하는 오프라인 테스트.

실행:  python -m unittest tests.test_offline -v
(외부 호출은 전부 가짜(mock)로 대체합니다. 실제 API 동작은 check_setup.py로 확인하세요.)
"""
import unittest
from datetime import date, datetime, timedelta, timezone
from email.utils import format_datetime
from unittest.mock import patch


class FakeStore:
    """chromadb/임베딩 모델 없이 쓰는 가짜 벡터DB (글자 겹침 점수로 검색)."""

    def __init__(self):
        self.docs = []

    def add_documents(self, docs):
        self.docs += docs

    def search(self, query, top_k=5, source_filter=None, where=None):
        pool = [d for d in self.docs if not where or all(d["metadata"].get(k) == v for k, v in where.items())]
        q = set(query.replace(" ", ""))
        scored = sorted(pool, key=lambda d: -len(q & set(d["text"].replace(" ", ""))))
        return [{"text": d["text"], "metadata": d["metadata"], "distance": 0.0} for d in scored[:top_k]]

    def delete(self, where):
        self.docs = [d for d in self.docs if not all(d["metadata"].get(k) == v for k, v in where.items())]


class FakeRanker:
    """임베딩 모델 없이 쓰는 가짜 순위 계산기 (글자 겹침 점수)."""

    def rank(self, items, query):
        q = set(query.replace(" ", ""))
        return [k for k, _ in sorted(items, key=lambda it: -len(q & set(it[1].replace(" ", ""))))]


def _place(cid, title, ctype="관광지", addr="부산 해운대구", **kw):
    p = {"source": "tourism", "content_id": cid, "title": title, "addr": addr, "content_type_id": "12",
         "content_type": ctype, "mapx": "129.1", "mapy": "35.1", "image": "", "modified_time": "",
         "event_start": "", "event_end": "", "overview": "", "raw": {}}
    p.update(kw)
    return p


def _news(days_ago, title, desc="", link=None):
    dt = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return {"source": "naver_news", "title": title, "description": desc,
            "link": link or f"http://x/{title}", "pub_date": format_datetime(dt), "raw": {}}


class RegionTests(unittest.TestCase):
    def test_normalize(self):
        from travel.regions import normalize_region
        self.assertEqual(normalize_region("부산"), "부산")
        self.assertEqual(normalize_region("부산광역시"), "부산")
        self.assertEqual(normalize_region("제주도"), "제주")
        self.assertEqual(normalize_region("전라북도"), "전북")
        self.assertEqual(normalize_region("이번 주말 강원특별자치도 갈래"), "강원")
        self.assertIsNone(normalize_region("파리"))


class WeatherTests(unittest.TestCase):
    def test_base_time(self):
        from collectors.weather import latest_base_datetime
        self.assertEqual(latest_base_datetime(datetime(2026, 9, 28, 6, 0)), ("20260928", "0500"))
        self.assertEqual(latest_base_datetime(datetime(2026, 9, 28, 5, 10)), ("20260928", "0200"))  # 5시 발표는 아직
        self.assertEqual(latest_base_datetime(datetime(2026, 9, 28, 1, 0)), ("20260927", "2300"))   # 전날 마지막 발표

    def test_summarize(self):
        from collectors.weather import summarize_daily
        rows = [
            {"fcst_date": "20260929", "category": "TMP", "value": "18"},
            {"fcst_date": "20260929", "category": "TMP", "value": "25"},
            {"fcst_date": "20260929", "category": "POP", "value": "60"},
            {"fcst_date": "20260929", "category": "PTY", "value": "1"},
            {"fcst_date": "20260929", "category": "SKY", "value": "4"},
            {"fcst_date": "20260929", "category": "SKY", "value": "4"},
            {"fcst_date": "20260929", "category": "SKY", "value": "1"},
        ]
        d = summarize_daily(rows)[0]
        self.assertEqual((d["date"], d["tmin"], d["tmax"], d["pop_max"]), ("2026-09-29", 18, 25, 60))
        self.assertEqual((d["precip"], d["sky"]), ("비", "흐림"))


class BaseClientTests(unittest.TestCase):
    def test_error_detection(self):
        from collectors.base_client import PublicDataAPIError, _raise_if_error
        with self.assertRaises(PublicDataAPIError):
            _raise_if_error({"OpenAPI_ServiceResponse": {"cmmMsgHeader": {
                "returnAuthMsg": "SERVICE_KEY_IS_NOT_REGISTERED_ERROR", "returnReasonCode": "30"}}})
        with self.assertRaises(PublicDataAPIError):
            _raise_if_error({"response": {"header": {"resultCode": "22", "resultMsg": "LIMITED_NUMBER_OF_SERVICE_REQUESTS_EXCEEDS_ERROR"}}})
        _raise_if_error({"response": {"header": {"resultCode": "0000", "resultMsg": "OK"}}})      # 정상
        _raise_if_error({"response": {"header": {"resultCode": "03", "resultMsg": "NO_DATA"}}})   # 데이터 없음은 통과

    def test_key_is_decoded_once(self):
        import collectors.base_client as bc
        with patch.object(bc, "PUBLIC_DATA_API_KEY", "abc%2Bdef%3D%3D"):
            self.assertEqual(bc._service_key(), "abc+def==")


class TourismTests(unittest.TestCase):
    def test_parse(self):
        import collectors.tourism as t
        payload = {"response": {"header": {"resultCode": "0000"}, "body": {"items": {"item": [
            {"contentid": "1", "title": "해운대해수욕장", "addr1": "부산 해운대구", "addr2": "우동",
             "contenttypeid": "12", "mapx": "129.16", "mapy": "35.15", "firstimage": "http://img"}]}}}}
        with patch.object(t, "call_public_api", return_value=payload) as m:
            places = t.get_tourism_info(l_dong_regn_cd="26", content_type_id="12", num_rows=5)
        self.assertEqual(places[0]["title"], "해운대해수욕장")
        self.assertEqual(places[0]["content_type"], "관광지")
        self.assertEqual(places[0]["addr"], "부산 해운대구 우동")
        self.assertEqual(m.call_args[0][1]["lDongRegnCd"], "26")

    def test_overview_stops_after_first_failure(self):
        import collectors.tourism as t
        places = [_place(str(i), f"장소{i}") for i in range(5)]
        with patch.object(t, "_load_cache", return_value={}), \
             patch.object(t, "get_overview", side_effect=RuntimeError("bad param")) as m:
            warns = t.enrich_overviews(places, limit=5)
        self.assertEqual(m.call_count, 1)  # 첫 호출 실패 시 나머지는 호출하지 않음
        self.assertTrue(warns)


class RiskScannerTests(unittest.TestCase):
    def test_scan_filters_and_flags(self):
        import travel.risk_scanner as rs

        def fake_search(query, display=10, sort="date"):
            if "태풍" in query:
                return [_news(1, "부산 태풍 특보 발효, 해운대해수욕장 입욕 통제", "부산 해안 통제"),
                        _news(20, "부산 태풍 과거 기사"),               # 오래됨 → 제외
                        _news(1, "서울 태풍 소식", "서울 얘기")]          # 지역 무관 → 제외
            if "축제 취소" in query:
                return [_news(2, "부산 불꽃축제 취소", "부산 행사 안전 문제로 취소")]
            return []

        with patch.object(rs, "search_news", side_effect=fake_search):
            items, warns = rs.scan_regional_risks("부산", days_back=7)
        titles = [i["title"] for i in items]
        self.assertEqual(len(items), 2)
        self.assertIn("부산 불꽃축제 취소", titles)
        self.assertFalse(any("과거" in t or "서울" in t for t in titles))
        self.assertEqual([i["id"] for i in items], ["N1", "N2"])

        places = [_place("1", "해운대해수욕장"), _place("2", "광안리해수욕장")]
        rs.flag_place_issues(places, items)
        self.assertTrue(places[0]["related_news_ids"])
        self.assertEqual(places[1]["related_news_ids"], [])

    def test_all_failures_returns_warning(self):
        import travel.risk_scanner as rs
        with patch.object(rs, "search_news", side_effect=ValueError("NAVER 키 없음")):
            items, warns = rs.scan_regional_risks("부산")
        self.assertEqual(items, [])
        self.assertTrue(warns)


class PipelineTests(unittest.TestCase):
    TODAY = date(2026, 9, 28)

    def _run(self, llm_result, weather_rows=None, places=None, news=None, **kw):
        import travel.pipeline as pl
        places = places if places is not None else [
            _place("1", "해운대해수욕장", overview="부산 대표 해변"),
            _place("2", "광안리해수욕장", overview="야경이 좋은 바다"),
            _place("3", "감천문화마을", ctype="문화시설", addr="부산 사하구"),
        ]
        news = news if news is not None else []
        with patch.object(pl, "resolve_ldong", return_value=("26", False)), \
             patch.object(pl, "get_tourism_info", side_effect=lambda **k: [dict(p) for p in places] if k["content_type_id"] == "12" else []), \
             patch.object(pl, "get_festivals", return_value=[]), \
             patch.object(pl, "scan_regional_risks", return_value=(news, [])), \
             patch.object(pl, "enrich_overviews", return_value=[]), \
             patch.object(pl, "get_short_term_forecast", return_value=weather_rows or []), \
             patch.object(pl, "chat_json", return_value=llm_result):
            return pl.recommend_trip("부산", kw.pop("start", "2026-10-20"), kw.pop("end", "2026-10-22"),
                                     preferences=kw.pop("preferences", "바다 야경"),
                                     store=FakeStore(), today=self.TODAY, **kw)

    def test_hallucinated_candidate_is_dropped(self):
        llm = ({"summary": "요약", "recommendations": [
            {"candidate_id": "C1", "reason": "좋아요", "risk_note": ""},
            {"candidate_id": "C99", "reason": "가짜 장소", "risk_note": ""}],
            "risks": [], "caveats": ["모델 제약"]}, "{}")
        res = self._run(llm)
        self.assertEqual(len(res["recommendations"]), 1)
        self.assertEqual(res["recommendations"][0]["rank"], 1)
        self.assertIn("모델 제약", res["caveats"])
        self.assertTrue(any("단기예보" in c for c in res["caveats"]))  # 10/20은 예보 범위 밖

    def test_risks_are_grounded_in_news(self):
        news = [{"id": "N1", "category": "기상", "keyword": "태풍", "title": "부산 태풍 특보",
                 "description": "해운대해수욕장 통제", "link": "http://n1", "pub_date": "2026-09-28 09:00"}]
        llm = ({"summary": "s", "recommendations": [{"candidate_id": "C1", "reason": "r", "risk_note": ""}],
                "risks": [{"news_id": "N1", "level": "HIGH", "detail": "입욕 통제"},
                          {"news_id": "N7", "level": "high", "detail": "존재하지 않는 기사"}],
                "caveats": []}, "{}")
        res = self._run(llm, news=news)
        self.assertEqual(len(res["risks"]), 1)
        self.assertEqual(res["risks"][0]["level"], "high")
        self.assertEqual(res["risks"][0]["link"], "http://n1")
        self.assertIn("naver_news", res["used_sources"])

    def test_llm_json_failure_falls_back(self):
        res = self._run((None, "죄송합니다 JSON이 아닙니다"))
        self.assertEqual(len(res["recommendations"]), 3)
        self.assertFalse(res["meta"]["llm_json_ok"])
        self.assertTrue(any("유효한 추천" in c for c in res["caveats"]))

    def test_weather_included_when_in_range(self):
        rows = [{"fcst_date": "20260929", "category": "TMP", "value": "20"},
                {"fcst_date": "20260929", "category": "POP", "value": "10"}]
        llm = ({"summary": "s", "recommendations": [], "risks": [], "caveats": []}, "{}")
        res = self._run(llm, weather_rows=rows, start="2026-09-29", end="2026-09-29")
        self.assertEqual(res["weather"][0]["date"], "2026-09-29")
        self.assertIn("weather", res["used_sources"])

    def test_no_candidates_skips_llm(self):
        import travel.pipeline as pl
        with patch.object(pl, "resolve_ldong", return_value=("26", False)), \
             patch.object(pl, "get_tourism_info", return_value=[]), \
             patch.object(pl, "get_festivals", return_value=[]), \
             patch.object(pl, "scan_regional_risks", return_value=([], [])), \
             patch.object(pl, "get_short_term_forecast", return_value=[]), \
             patch.object(pl, "chat_json", side_effect=AssertionError("LLM을 호출하면 안 됨")):
            res = pl.recommend_trip("부산", "2026-10-20", "2026-10-21", store=FakeStore(), today=self.TODAY)
        self.assertEqual(res["recommendations"], [])

    def test_invalid_inputs(self):
        import travel.pipeline as pl
        with self.assertRaises(ValueError):
            pl.recommend_trip("파리", "2026-10-20", "2026-10-21", store=FakeStore())
        with self.assertRaises(ValueError):
            pl.recommend_trip("부산", "2026-10-22", "2026-10-20", store=FakeStore())

    def test_area_filter(self):
        llm = ({"summary": "s", "recommendations": [{"candidate_id": "C1", "reason": "r", "risk_note": ""}],
                "risks": [], "caveats": []}, "{}")
        res = self._run(llm, area="사하구")
        self.assertEqual(res["meta"]["candidates"], 1)
        self.assertEqual(res["recommendations"][0]["name"], "감천문화마을")


class JsonParseTests(unittest.TestCase):
    def test_parse_variants(self):
        from llm.ollama_client import _parse_json
        self.assertEqual(_parse_json('{"a": 1}'), {"a": 1})
        self.assertEqual(_parse_json('```json\n{"a": 1}\n```'), {"a": 1})
        self.assertEqual(_parse_json('결과는 다음과 같습니다: {"a": 1} 이상입니다'), {"a": 1})
        self.assertIsNone(_parse_json("json 아님"))
        self.assertIsNone(_parse_json("[1, 2]"))


if __name__ == "__main__":
    unittest.main()
