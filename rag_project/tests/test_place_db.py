"""장소 벡터 DB (travel/place_db.py) — 실제 임베딩 모델·TourAPI 없이 가짜 벡터로 확인"""
import hashlib
import os
import tempfile
import time
import unittest
from unittest.mock import patch

import numpy as np

import config
from travel import pipeline as pl
from travel import place_db
from travel.context import rank_places
from travel.embeddings import PlaceRanker
from travel.place_db import PlaceDB


def fake_embed(texts):
    """글자를 32칸에 나눠 센 뒤 정규화 (비슷한 글자가 많으면 비슷한 벡터)"""
    out = []
    for t in texts:
        v = np.zeros(32, dtype=np.float32)
        for ch in t:
            v[int(hashlib.md5(ch.encode()).hexdigest(), 16) % 32] += 1
        out.append(v / (np.linalg.norm(v) or 1))
    return np.stack(out)


def place(cid, title, ctype="12", addr="부산광역시 해운대구 우동"):
    return {"source": "tourism", "content_id": cid, "title": title, "addr": addr, "content_type_id": ctype,
            "content_type": {"12": "관광지", "14": "문화시설", "15": "축제공연행사", "39": "음식점"}[ctype],
            "mapx": "129.1", "mapy": "35.1", "image": "", "modified_time": f"2026010{cid[-1]}",
            "event_start": "", "event_end": "", "overview": "", "raw": {"lclsSystm1": "NA", "big": "x" * 50}}


class PlaceDBTests(unittest.TestCase):
    def setUp(self):
        self.calls = []

        def embed(texts):
            self.calls.append(list(texts))
            return fake_embed(texts)

        self.db = PlaceDB(tempfile.mkdtemp(prefix="placedb_"), embed=embed)

    def test_save_and_load_region(self):
        n = self.db.put_region("26", "350", [place("1", "해운대해수욕장"), place("2", "부산 불꽃축제", "15"),
                                             place("3", "해운대 시장 국밥", "39")], lambda p: "부산")
        self.assertEqual(n, 2)  # 축제는 저장하지 않는다
        got = self.db.get_places("26", "350")
        self.assertEqual({p["title"] for p in got}, {"해운대해수욕장", "해운대 시장 국밥"})
        self.assertEqual(got[0]["content_id"], "3")  # 최근 수정순
        self.assertEqual(got[1]["raw"]["lclsSystm1"], "NA")
        self.assertNotIn("big", got[1]["raw"])  # 원본 응답은 필요한 값만 남긴다
        self.assertTrue(self.db.is_fresh("26", "350"))
        self.assertFalse(self.db.is_fresh("26", "999"))
        self.assertEqual([p["title"] for p in self.db.get_places("26", types={"39"})], ["해운대 시장 국밥"])

    def test_reuses_vectors_and_removes_closed_places(self):
        self.db.put_region("26", "350", [place("1", "해운대해수욕장"), place("2", "동백섬")], lambda p: "부산")
        self.calls.clear()
        self.db.put_region("26", "350", [place("1", "해운대해수욕장"), place("4", "더베이101")], lambda p: "부산")
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(len(self.calls[0]), 1)  # 새 장소만 계산
        self.assertEqual({p["title"] for p in self.db.get_places("26", "350")}, {"해운대해수욕장", "더베이101"})

    def test_search(self):
        self.db.put_region("26", "350", [place("1", "해운대해수욕장"), place("4", "국립해양박물관", "14")], lambda p: "부산")
        hits = self.db.search("국립해양박물관", "26", k=2)
        self.assertEqual(hits[0]["title"], "국립해양박물관")

    def test_stale_after_max_age(self):
        self.db.put_region("26", "350", [place("1", "해운대해수욕장")], lambda p: "부산")
        self.db._regions["26|350"] = time.time() - (config.PLACE_DB_MAX_AGE_DAYS + 1) * 86400
        self.assertFalse(self.db.is_fresh("26", "350"))


class PipelineWithDBTests(unittest.TestCase):
    def setUp(self):
        self.db = PlaceDB(tempfile.mkdtemp(prefix="placedb_"), embed=fake_embed)
        place_db.reset_for_tests(self.db)
        self.on = patch.object(config, "PLACE_DB_ENABLED", True)
        self.on.start()

    def tearDown(self):
        self.on.stop()
        place_db.reset_for_tests(None)

    def test_first_from_api_then_from_db(self):
        api = [place("1", "해운대해수욕장"), place("3", "해운대 시장 국밥", "39")]
        with patch.object(pl, "get_tourism_info", return_value=api) as m:
            first = pl._area_places("부산", "26", "350", False)
            second = pl._area_places("부산", "26", "350", False)
        self.assertEqual(m.call_count, 1)  # 두 번째는 DB에서
        self.assertEqual(len(first), 2)
        self.assertEqual({p["title"] for p in second}, {"해운대해수욕장", "해운대 시장 국밥"})

    def test_api_failure_uses_old_db(self):
        self.db.put_region("26", "350", [place("1", "해운대해수욕장")], lambda p: "부산")
        self.db._regions["26|350"] = 0  # 아주 오래됨
        with patch.object(pl, "get_tourism_info", side_effect=TimeoutError("느림")):
            got = pl._area_places("부산", "26", "350", False)
        self.assertEqual([p["title"] for p in got], ["해운대해수욕장"])

    def test_api_failure_without_db_raises(self):
        with patch.object(pl, "get_tourism_info", side_effect=TimeoutError("느림")):
            with self.assertRaises(TimeoutError):
                pl._area_places("부산", "26", "350", False)

    def test_whole_sido_from_db(self):
        self.db.put_region("26", "350", [place("1", "해운대해수욕장")], lambda p: "부산")
        self.db.put_region("26", "140", [place("5", "자갈치시장", addr="부산광역시 중구")], lambda p: "부산")
        with patch("collectors.tourism.fetch_ldong_sigungu", return_value={"해운대구": "350", "중구": "140"}):
            got = pl._db_sido_places("부산", "26", False)
        self.assertEqual({p["title"] for p in got}, {"해운대해수욕장", "자갈치시장"})
        with patch("collectors.tourism.fetch_ldong_sigungu", return_value={"해운대구": "350", "중구": "140", "서구": "110"}):
            self.assertEqual(pl._db_sido_places("부산", "26", False), [])  # 하나라도 없으면 TourAPI로

    def test_ranking_uses_db_vectors(self):
        places = [place("1", "해운대해수욕장"), place("4", "국립해양박물관", "14")]
        self.db.put_region("26", "350", places, lambda p: "부산")
        ranker = PlaceRanker(cache_path=os.path.join(tempfile.mkdtemp(), "e.npz"))
        seen = []

        def embed(texts):
            seen.append(list(texts))
            return fake_embed(texts)

        with patch.object(ranker, "_embed", side_effect=embed):
            ranked = rank_places([dict(p) for p in places], "부산", "국립해양박물관", ranker)
        self.assertEqual(ranked[0]["title"], "국립해양박물관")
        self.assertEqual(seen, [["국립해양박물관"]])  # 장소 벡터는 DB 것을 쓰고 질문만 계산


if __name__ == "__main__":
    unittest.main()
