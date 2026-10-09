"""장애 대응(재시도, 오류 문구, 0건 처리) 오프라인 테스트."""
import os
import subprocess
import sys
import unittest
from datetime import date
from unittest.mock import MagicMock, patch

import requests

from tests.test_offline import FakeRanker, _place

TODAY = date(2026, 10, 6)


def _resp(status=200, payload=None, text=""):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = payload if payload is not None else {}
    r.text = text
    r.headers = {"Content-Type": "application/json"}
    r.url = "http://x"
    return r


class BaseClientResilienceTests(unittest.TestCase):
    def setUp(self):
        import collectors.base_client as bc
        self.bc = bc
        p = patch.object(bc, "PUBLIC_DATA_API_KEY", "KEY1234567890123456789012345")
        p.start(); self.addCleanup(p.stop)
        s = patch.object(bc.time, "sleep"); s.start(); self.addCleanup(s.stop)

    def test_retries_timeout_once_then_succeeds(self):
        ok = _resp(payload={"response": {"header": {"resultCode": "0000"}, "body": {"items": ""}}})
        with patch.object(self.bc.requests, "get", side_effect=[requests.exceptions.ReadTimeout(), ok]) as g:
            self.bc.call_public_api("http://x/api", {})
        self.assertEqual(g.call_count, 2)

    def test_timeout_after_retry_becomes_readable_error(self):
        with patch.object(self.bc.requests, "get", side_effect=requests.exceptions.ReadTimeout()):
            with self.assertRaises(self.bc.PublicDataAPIError) as cm:
                self.bc.call_public_api("http://x/getMinuDustFrcstDspth", {}, timeout=30)
        self.assertIn("30초", str(cm.exception))
        self.assertIn("getMinuDustFrcstDspth", str(cm.exception))

    def test_top_level_error_json_is_not_silently_empty(self):
        # response 래퍼 없이 오류만 오는 게이트웨이 응답이 '0건'으로 오인되면 안 된다
        with self.assertRaises(self.bc.PublicDataAPIError):
            self.bc._raise_if_error({"resultCode": "401", "resultMsg": "Unauthorized"})
        self.bc._raise_if_error({"resultCode": "0000", "resultMsg": "OK"})


class RequestParamTests(unittest.TestCase):
    """TourAPI는 모르는 파라미터(type 등)를 INVALID_REQUEST_PARAMETER_ERROR로 거절한다 (실제로 겪은 문제)."""

    def test_json_request_sends_only__type(self):
        import collectors.base_client as bc
        ok = _resp(payload={"response": {"header": {"resultCode": "0000"}, "body": {"items": ""}}})
        with patch.object(bc, "PUBLIC_DATA_API_KEY", "K" * 30), patch.object(bc.requests, "get", return_value=ok) as g:
            bc.call_public_api("http://x/api", {"a": 1})
        params = g.call_args.kwargs["params"]
        self.assertEqual(params["_type"], "json")
        self.assertNotIn("type", params)

    def test_tourism_request_params_are_clean(self):
        import collectors.base_client as bc
        import collectors.tourism as t
        payload = {"response": {"header": {"resultCode": "0000"}, "body": {"items": {"item": [
            {"contentid": "1", "title": "장소", "addr1": "부산", "contenttypeid": "12"}]}}}}
        with patch.object(bc, "PUBLIC_DATA_API_KEY", "K" * 30), patch.object(bc.requests, "get", return_value=_resp(payload=payload)) as g:
            places = t.get_tourism_info(l_dong_regn_cd="26", content_type_id="12", num_rows=3)
        self.assertEqual(len(places), 1)
        params = g.call_args.kwargs["params"]
        self.assertNotIn("type", params)
        self.assertEqual(params["lDongRegnCd"], "26")


class NaverResilienceTests(unittest.TestCase):
    def setUp(self):
        import collectors.naver_news as nn
        self.nn = nn
        for p in (patch.object(nn, "NAVER_CLIENT_ID", "id"), patch.object(nn, "NAVER_CLIENT_SECRET", "secret"),
                  patch.object(nn.time, "sleep")):
            p.start(); self.addCleanup(p.stop)

    def test_429_is_retried(self):
        ok = _resp(payload={"items": [{"title": "<b>부산</b> 특보", "description": "d", "link": "l", "originallink": "o", "pubDate": "x"}]})
        with patch.object(self.nn.requests, "get", side_effect=[_resp(429), ok]) as g:
            res = self.nn.search_news("부산 특보")
        self.assertEqual(g.call_count, 2)
        self.assertEqual(res[0]["title"], "부산 특보")

    def test_401_shows_server_message(self):
        bad = _resp(401, payload={"errorMessage": "NID AUTH Result Invalid (1000)", "errorCode": "024"})
        with patch.object(self.nn.requests, "get", return_value=bad):
            with self.assertRaises(requests.HTTPError) as cm:
                self.nn.search_news("부산")
        self.assertIn("401", str(cm.exception))
        self.assertIn("NID AUTH", str(cm.exception))


class NaverHubTests(unittest.TestCase):
    """검색 API는 NAVER API HUB로만 호출한다 (옛 주소/헤더로 보내면 401이 났던 문제)."""

    OK = {"items": [{"title": "t", "description": "d", "link": "l", "originallink": "o", "pubDate": "x"}]}

    def setUp(self):
        import collectors.naver_news as nn
        self.nn = nn
        for p in (patch.object(nn, "NAVER_CLIENT_ID", "my-id"), patch.object(nn, "NAVER_CLIENT_SECRET", "my-secret"),
                  patch.object(nn.time, "sleep")):
            p.start(); self.addCleanup(p.stop)

    def test_news_uses_hub_url_and_ncp_headers(self):
        with patch.object(self.nn.requests, "get", return_value=_resp(payload=self.OK)) as g:
            self.nn.search_news("부산")
        headers = g.call_args.kwargs["headers"]
        self.assertEqual(g.call_args.args[0], "https://naverapihub.apigw.ntruss.com/search/v1/news")
        self.assertEqual(headers["X-NCP-APIGW-API-KEY-ID"], "my-id")
        self.assertEqual(headers["X-NCP-APIGW-API-KEY"], "my-secret")
        self.assertNotIn("X-Naver-Client-Id", headers)

    def test_auth_failure_is_reported_once_with_hint(self):
        bad = _resp(401, payload={"errorMessage": "bad key"})
        with patch.object(self.nn.requests, "get", return_value=bad) as g:
            with self.assertRaises(requests.HTTPError) as cm:
                self.nn.search_news("부산")
        self.assertEqual(g.call_count, 1)  # 재시도/다른 방식 시도 없이 바로 알려준다
        self.assertIn("401", str(cm.exception))
        self.assertIn("뉴스", str(cm.exception))

    def test_trend_api_uses_hub_url_and_json_header(self):
        with patch.object(self.nn.requests, "post", return_value=_resp(payload={"results": []})) as g:
            self.nn.get_search_trend([{"groupName": "a", "keywords": ["b"]}], "2026-10-01", "2026-10-05")
        self.assertEqual(g.call_args.args[0], "https://naverapihub.apigw.ntruss.com/search-trend/v1/search")
        self.assertEqual(g.call_args.kwargs["headers"]["Content-Type"], "application/json")

    def test_missing_keys_message_points_to_hub(self):
        with patch.object(self.nn, "NAVER_CLIENT_ID", ""):
            with self.assertRaises(ValueError) as cm:
                self.nn.search_news("부산")
        self.assertIn("NAVER API HUB", str(cm.exception))


class ZeroCandidatesTests(unittest.TestCase):
    def test_zero_results_explains_what_was_tried(self):
        import travel.pipeline as pl
        with patch.object(pl, "resolve_ldong", return_value=("26", False)), \
             patch.object(pl, "get_tourism_info", return_value=[]), \
             patch.object(pl, "get_festivals", return_value=[]):
            places, warns = pl._collect_candidates("부산", TODAY, TODAY, False, "")
        self.assertEqual(places, [])
        self.assertTrue(any("0건" in w and "lDongRegnCd=26" in w and "areaCode=6" in w for w in warns), warns)

    def test_falls_back_to_legacy_area_code(self):
        import travel.pipeline as pl

        def fake(**k):
            return [dict(_place("9", "부산구방식장소"), indoor=False)] if k.get("area_code") == "6" and k["content_type_id"] == "12" else []

        with patch.object(pl, "resolve_ldong", return_value=("26", False)), \
             patch.object(pl, "get_tourism_info", side_effect=fake), patch.object(pl, "get_festivals", return_value=[]):
            places, warns = pl._collect_candidates("부산", TODAY, TODAY, False, "")
        self.assertEqual([p["title"] for p in places], ["부산구방식장소"])
        self.assertTrue(any("구 방식" in w for w in warns))


class ChatZeroPlacesTests(unittest.TestCase):
    def test_no_places_gives_explanation_not_empty_days_and_retries_next_time(self):
        import time
        import travel.chat as chat
        calls = {"n": 0}

        def fake_gather(sido, area, start, end, include_food, today):
            calls["n"] += 1
            return {
                "sido": sido, "area": area, "start": start.isoformat(), "end": end.isoformat(), "include_food": False,
                "places": [], "news": [], "weather": [{"date": "2026-10-07", "tmin": 13, "tmax": 25, "pop_max": 0, "precip": "없음", "sky": "맑음"}],
                "weather_status": "ok", "air": {"by_date": {}, "realtime": None, "warnings": []},
                "warnings": ["관광정보 조회는 성공했지만 결과가 0건이에요"], "fetched_at": time.time(),
            }

        with patch.object(chat, "chat_json_messages", side_effect=RuntimeError("down")), \
             patch.object(chat, "gather_raw", side_effect=fake_gather), patch.object(chat, "enrich", return_value=[]):
            s = chat.ChatSession()
            chat.handle_message(s, "부산 가려고요", today=TODAY, ranker=FakeRanker())
            chat.handle_message(s, "내일 당일치기", today=TODAY, ranker=FakeRanker())   # 취향을 한 번 묻는다
            r = chat.handle_message(s, "상관없어요", today=TODAY, ranker=FakeRanker())  # → 일정 생성 시도 → 후보 0건
            self.assertEqual(r["stage"], "asking")
            self.assertIn("일정에 넣을 장소를 찾지 못했어요", r["reply"])
            from tests.test_chat import body
            for internal in ("개발자", "diagnose", "API", "제약", "⚠️"):
                self.assertNotIn(internal, body(r["reply"]))   # 사용자에게 내부 사정을 알리지 않는다 (고정 하단 서식은 제외)
            self.assertNotIn("일정 없음", r["reply"])
            self.assertTrue(any("0건" in c for c in r["caveats"]))
            self.assertIsNone(s.raw)  # 빈 결과를 캐시하지 않는다
            chat.handle_message(s, "다시 해줘", today=TODAY, ranker=FakeRanker())
            self.assertEqual(calls["n"], 2)  # 다음 요청에서 다시 수집


class OllamaPayloadTests(unittest.TestCase):
    def test_keep_alive_is_sent_so_model_stays_loaded(self):
        import llm.ollama_client as oc
        ok = MagicMock(); ok.status_code = 200; ok.json.return_value = {"message": {"content": "{}"}}
        with patch.object(oc.requests, "post", return_value=ok) as g:
            oc._post_chat([{"role": "user", "content": "hi"}])
        payload = g.call_args.kwargs["json"]
        self.assertEqual(payload["keep_alive"], oc.OLLAMA_KEEP_ALIVE)
        self.assertEqual(payload["options"]["num_ctx"], oc.OLLAMA_NUM_CTX)


class PlaceRankerTests(unittest.TestCase):
    """임베딩 모델 없이, 글자 빈도 벡터로 '한 번 계산한 장소는 다시 계산하지 않는지'를 검증."""

    def make(self, path):
        import numpy as np
        from travel.embeddings import PlaceRanker

        class FakeEmbedRanker(PlaceRanker):
            def __init__(self, *a, **k):
                super().__init__(*a, **k)
                self.embedded: list[str] = []

            def _load_model(self):
                pass

            def _embed(self, texts):
                self.embedded += texts
                out = np.zeros((len(texts), 64), dtype=np.float32)
                for i, t in enumerate(texts):
                    for ch in t:
                        out[i, ord(ch) % 64] += 1
                    n = np.linalg.norm(out[i])
                    out[i] /= n if n else 1
                return out

        return FakeEmbedRanker(model_name="fake", cache_path=path)

    ITEMS = [("1", "[관광지-부산] 해운대 바다 해변"), ("2", "[문화시설-부산] 박물관 전시관"), ("3", "[관광지-부산] 공원 산책로")]

    def setUp(self):
        import tempfile
        self.path = os.path.join(tempfile.mkdtemp(prefix="rank_test_"), "emb.npz")

    def test_ranks_by_similarity(self):
        r = self.make(self.path)
        self.assertEqual(r.rank(self.ITEMS, "바다 해변")[0], "1")
        self.assertEqual(r.rank(self.ITEMS, "박물관 전시")[0], "2")

    def test_known_places_are_not_embedded_again(self):
        r = self.make(self.path)
        r.rank(self.ITEMS, "바다")
        r.embedded.clear()
        r.rank(self.ITEMS, "산책")
        self.assertEqual(r.embedded, ["산책"])  # 질문 하나만 계산

    def test_cache_survives_restart(self):
        self.make(self.path).rank(self.ITEMS, "바다")
        again = self.make(self.path)  # 프로그램을 다시 켠 것과 같은 상황
        again.rank(self.ITEMS, "바다")
        self.assertEqual(again.embedded, ["바다"])

    def test_changed_text_is_recomputed(self):
        r = self.make(self.path)
        r.rank(self.ITEMS, "바다")
        r.embedded.clear()
        r.rank([("1", "[관광지-부산] 해운대 바다 해변 | 주소: 새 주소")] + self.ITEMS[1:], "바다")
        self.assertEqual(len(r.embedded), 2)  # 바뀐 장소 1곳 + 질문

    def test_model_change_invalidates_cache(self):
        from travel.embeddings import PlaceRanker
        self.make(self.path).rank(self.ITEMS, "바다")
        other = self.make(self.path)
        other._model_name = "other-model"
        other.rank(self.ITEMS, "바다")
        self.assertEqual(len(other.embedded), 4)  # 장소 3 + 질문 1: 다른 모델의 벡터는 쓰지 않는다

    def test_rank_places_falls_back_to_keywords_on_failure(self):
        import travel.context as ctx

        class Broken:
            def rank(self, *a, **k):
                raise RuntimeError("no model")

        places = [dict(_place("1", "박물관"), indoor=True), dict(_place("2", "해운대 바다 해변"), indoor=False)]
        out = ctx.rank_places(places, "부산", "바다 해변", Broken())
        self.assertEqual(out[0]["title"], "해운대 바다 해변")


class CacheTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        import collectors.cache as cache
        self.cache = cache
        self.tmp = tempfile.mkdtemp(prefix="cache_test_")
        for p in (patch.object(cache.config, "API_CACHE_ENABLED", True), patch.object(cache.config, "API_CACHE_DIR", self.tmp)):
            p.start(); self.addCleanup(p.stop)
        cache.clear_memory()
        self.addCleanup(cache.clear_memory)

    def test_second_call_does_not_hit_the_api(self):
        calls = {"n": 0}

        @self.cache.ttl_cache("t1", 60)
        def fetch(x):
            calls["n"] += 1
            return [{"x": x}]

        self.assertEqual(fetch(1), [{"x": 1}])
        self.assertEqual(fetch(1), [{"x": 1}])
        self.assertEqual(calls["n"], 1)
        fetch(2)
        self.assertEqual(calls["n"], 2)  # 인자가 다르면 별도 캐시

    def test_survives_restart_via_file(self):
        calls = {"n": 0}

        @self.cache.ttl_cache("t2", 60)
        def fetch():
            calls["n"] += 1
            return {"a": 1}

        fetch()
        self.cache.clear_memory()  # 프로그램을 껐다 켠 것과 같은 상황
        self.assertEqual(fetch(), {"a": 1})
        self.assertEqual(calls["n"], 1)

    def test_empty_results_and_errors_are_not_cached(self):
        calls = {"n": 0}

        @self.cache.ttl_cache("t3", 60)
        def fetch():
            calls["n"] += 1
            if calls["n"] == 1:
                return []
            if calls["n"] == 2:
                raise RuntimeError("boom")
            return [1]

        self.assertEqual(fetch(), [])
        with self.assertRaises(RuntimeError):
            fetch()
        self.assertEqual(fetch(), [1])
        self.assertEqual(fetch(), [1])
        self.assertEqual(calls["n"], 3)

    def test_caller_mutation_does_not_corrupt_cache(self):
        @self.cache.ttl_cache("t4", 60)
        def fetch():
            return [{"title": "a"}]

        first = fetch()
        first[0]["indoor"] = True  # 파이프라인이 하는 것처럼 결과를 고쳐 쓴다
        self.assertNotIn("indoor", fetch()[0])

    def test_expired_entry_is_refetched(self):
        calls = {"n": 0}

        @self.cache.ttl_cache("t5", 10)
        def fetch():
            calls["n"] += 1
            return [calls["n"]]

        fetch()
        with patch.object(self.cache.time, "time", return_value=__import__("time").time() + 11):
            self.assertEqual(fetch(), [2])


class PlaceClassificationTests(unittest.TestCase):
    def test_busan_in_title_does_not_make_a_place_outdoor(self):
        """'산' 한 글자를 실외 키워드로 써서 '부산'이 들어간 모든 장소가 실외로 분류되던 버그."""
        from travel.places import is_indoor
        self.assertTrue(is_indoor({"title": "브릭캠퍼스 부산", "content_type_id": "14"}))
        self.assertTrue(is_indoor({"title": "부산시립미술관", "content_type_id": "14"}))
        self.assertFalse(is_indoor({"title": "부산 갈맷길 2코스", "content_type_id": "28"}))
        self.assertFalse(is_indoor({"title": "해운대해수욕장", "content_type_id": "12"}))


class SelectCandidatesTests(unittest.TestCase):
    def _ranked(self):
        def p(i, ty, indoor=False):
            return {"content_id": str(i), "title": f"p{i}", "content_type_id": ty, "indoor": indoor}
        # 유사도 순위: 레포츠가 상위를 독차지
        return [p(1, "28"), p(2, "28"), p(3, "28"), p(4, "28"), p(5, "12"), p(6, "14", True), p(7, "12")]

    def test_type_cap_keeps_variety(self):
        from travel.context import select_candidates
        chosen = select_candidates(self._ranked(), k=5, need_indoor=0, type_caps={"28": 2})
        self.assertEqual([c["title"] for c in chosen], ["p1", "p2", "p5", "p6", "p7"])

    def test_cap_is_relaxed_when_not_enough_candidates(self):
        from travel.context import select_candidates
        chosen = select_candidates(self._ranked(), k=7, need_indoor=0, type_caps={"28": 1})
        self.assertEqual(len(chosen), 7)  # 모자라면 상한에 걸린 것도 순위대로 채운다

    def test_indoor_guarantee(self):
        from travel.context import select_candidates
        chosen = select_candidates(self._ranked(), k=3, need_indoor=1)
        self.assertTrue(any(c["indoor"] for c in chosen))


class GatherDeadlineTests(unittest.TestCase):
    def test_slow_optional_source_does_not_block_everything(self):
        import time
        import travel.context as ctx

        def slow_air(*a, **k):
            time.sleep(0.4)
            return {"by_date": {"2026-10-07": {"pm10": "좋음"}}, "realtime": None, "warnings": []}

        place = dict(_place("1", "해운대해수욕장"), indoor=False)
        with patch.object(ctx, "GATHER_TIMEOUT_SEC", 0.1), \
             patch.object(ctx, "_collect_candidates", return_value=([place], [])), \
             patch.object(ctx, "scan_regional_risks", return_value=([], [])), \
             patch.object(ctx, "_collect_weather", return_value=([], "out_of_range", "")), \
             patch.object(ctx, "get_air_summary", side_effect=slow_air):
            t0 = time.perf_counter()
            raw = ctx.gather_raw("부산", "", TODAY, TODAY, False, TODAY)
            elapsed = time.perf_counter() - t0
        self.assertLess(elapsed, 0.3)                 # 느린 미세먼지를 끝까지 기다리지 않았다
        self.assertEqual(len(raw["places"]), 1)       # 나머지는 정상 반영
        self.assertTrue(any("미세먼지" in w and "끝나지 않아" in w for w in raw["warnings"]), raw["warnings"])
        self.assertIn("places", raw["timings"])


class OllamaStatsTests(unittest.TestCase):
    def _call(self, payload_data, think=""):
        import llm.ollama_client as oc
        ok = MagicMock(); ok.status_code = 200; ok.json.return_value = payload_data
        with patch.object(oc, "OLLAMA_THINK", think), patch.object(oc.requests, "post", return_value=ok) as g:
            out = oc._post_chat([{"role": "user", "content": "hi"}])
        return oc, out, g.call_args.kwargs["json"]

    def test_stats_show_speed_and_thinking(self):
        oc, out, _ = self._call({"message": {"content": "{}", "thinking": "abcde"}, "eval_count": 100,
                                 "eval_duration": 20_000_000_000, "prompt_eval_count": 500, "total_duration": 30_000_000_000})
        self.assertEqual(out, "{}")
        self.assertEqual(oc.LAST_STATS["tokens_per_sec"], 5.0)
        self.assertEqual(oc.LAST_STATS["thinking_chars"], 5)
        self.assertEqual(oc.LAST_STATS["total_sec"], 30.0)

    def test_think_option_is_sent_only_when_configured(self):
        _, _, default_payload = self._call({"message": {"content": "{}"}})
        self.assertNotIn("think", default_payload)  # 생각 기능이 없는 모델에 보내면 오류가 날 수 있어 기본은 생략
        _, _, off_payload = self._call({"message": {"content": "{}"}}, think="false")
        self.assertIs(off_payload["think"], False)


class FallbackOrderTests(unittest.TestCase):
    def test_fallback_demotes_leisure_sports_unless_activity_requested(self):
        import time
        import travel.chat as chat

        def places():
            a = dict(_place("1", "부산요트투어", ctype="레포츠"), content_type_id="28", indoor=False)
            b = dict(_place("2", "해운대해수욕장"), indoor=False)
            c = dict(_place("3", "청사포 기찻길"), indoor=False)
            return [a, b, c]  # 순위: 요트투어 > 해수욕장 > 기찻길

        def fake_gather(sido, area, start, end, include_food, today):
            return {"sido": sido, "area": area, "start": start.isoformat(), "end": end.isoformat(), "include_food": False,
                    "places": places(), "news": [], "weather": [], "weather_status": "out_of_range",
                    "air": {"by_date": {}, "realtime": None, "warnings": []}, "warnings": [], "fetched_at": time.time()}

        def first_day(text):
            with patch.object(chat, "chat_json_messages", side_effect=RuntimeError("down")), \
                 patch.object(chat, "gather_raw", side_effect=fake_gather), patch.object(chat, "enrich", return_value=[]):
                s = chat.ChatSession()
                chat.handle_message(s, "부산 가려고요", today=TODAY, ranker=FakeRanker())
                r = chat.handle_message(s, text, today=TODAY, ranker=FakeRanker())
            return [it["place"]["name"] for it in r["plan"][0]["items"] if it["place"]]

        quiet = first_day("내일 당일치기 조용히 걷고 싶어요")
        self.assertEqual(quiet[-1], "부산요트투어")           # 걷기 취향이면 레포츠는 맨 뒤
        active = first_day("내일 당일치기 요트 액티비티 하고 싶어요")
        self.assertEqual(active[0], "부산요트투어")          # 액티비티를 원하면 순위 그대로


class ConfigTests(unittest.TestCase):
    def test_trailing_slash_is_stripped_from_ollama_url(self):
        env = {**os.environ, "OLLAMA_BASE_URL": "http://192.168.0.14:11434/"}
        out = subprocess.run([sys.executable, "-c", "import config; print(config.OLLAMA_BASE_URL)"],
                             capture_output=True, text=True, env=env, cwd=os.path.dirname(os.path.dirname(__file__)))
        self.assertEqual(out.stdout.strip(), "http://192.168.0.14:11434")


if __name__ == "__main__":
    unittest.main()
