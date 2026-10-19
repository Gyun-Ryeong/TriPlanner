"""
지역 대표 사진(/region-photo) 오프라인 테스트.

    python -m unittest tests.test_photos -v
"""
import unittest
from unittest.mock import patch


def _p(cid, title, ctype="12", cat="NA", image="http://tong.visitkorea.or.kr/x.jpg", addr="강원 고성군"):
    return {"content_id": cid, "title": title, "content_type_id": ctype, "image": image, "addr": addr,
            "raw": {"lclsSystm1": cat, "lclsSystm2": cat + "01"}}


class RegionPhotoTests(unittest.TestCase):
    def setUp(self):
        import travel.photos as photos
        self.photos = photos
        photos._cache.clear()
        self.addCleanup(photos._cache.clear)

    def test_pick_prefers_nature_and_skips_experience_villages(self):
        pick = self.photos._pick([
            _p("1", "체험마을", cat="EX"), _p("2", "사진 없는 해변", image=""), _p("3", "향교", cat="HS"), _p("4", "화진포", cat="NA")])
        self.assertEqual(pick["title"], "화진포")
        self.assertIsNone(self.photos._pick([_p("1", "사진 없음", image="")]))

    def test_same_name_uses_the_app_region_and_returns_https(self):
        calls = []

        def fake_info(**kw):
            calls.append(kw)
            return [_p("1", "화진포해수욕장")]

        with patch.object(self.photos, "_resolve", side_effect=lambda n, r: ("강원", "고성") if r == "강원도" else ("경남", "고성")), \
                patch.object(self.photos, "resolve_ldong", return_value=("51", False)), \
                patch.object(self.photos, "resolve_sigungu", return_value=[("고성군", "820")]), \
                patch.object(self.photos, "get_tourism_info", side_effect=fake_info):
            r = self.photos.region_photo("고성", "강원도")
            self.assertEqual((r["sido"], r["area"], r["title"]), ("강원", "고성", "화진포해수욕장"))
            self.assertTrue(r["image"].startswith("https://"))
            self.photos.region_photo("고성", "강원도")
        self.assertEqual(len(calls), 1)  # 같은 지역은 기억해 두고 다시 조회하지 않음

    def test_api_failure_returns_empty_image(self):
        with patch.object(self.photos, "_resolve", return_value=("전남", "곡성")), \
                patch.object(self.photos, "resolve_ldong", side_effect=RuntimeError("api down")):
            r = self.photos.region_photo("곡성")
        self.assertEqual(r["image"], "")
        self.assertEqual(self.photos._cache, {})  # 실패는 기억하지 않는다

    def test_endpoint(self):
        from fastapi.testclient import TestClient
        import api_server
        with patch.object(api_server, "region_photo", return_value={"sido": "경기", "area": "성남", "image": "https://x", "title": "t", "credit": "c"}) as m:
            res = TestClient(api_server.app).get("/region-photo", params={"name": "성남", "region": "경기도 / 인천"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["area"], "성남")
        m.assert_called_once_with("성남", "경기도 / 인천")


if __name__ == "__main__":
    unittest.main()
