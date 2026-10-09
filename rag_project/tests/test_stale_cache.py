import unittest
from unittest import mock

import config
from collectors import cache


class StaleCacheTests(unittest.TestCase):
    def setUp(self):
        cache.clear_memory()
        self.p = mock.patch.object(config, "API_CACHE_ENABLED", True)
        self.p.start()
        self.calls = 0

    def tearDown(self):
        self.p.stop()
        cache.clear_memory()

    def test_stale_used_on_failure_and_cooldown(self):
        state = {"ok": True}

        @cache.ttl_cache("t_stale_a", 1, stale_ttl=1000, fail_cooldown=300)
        def f(x):
            self.calls += 1
            if not state["ok"]:
                raise RuntimeError("timeout")
            return [x]

        self.assertEqual(f(1), [1])
        with mock.patch("collectors.cache.time.time", return_value=__import__("time").time() + 10):
            state["ok"] = False
            self.assertEqual(f(1), [1])          # 실패 -> 저장본
            n = self.calls
            self.assertEqual(f(1), [1])          # 쿨다운 중 -> 재호출 없음
            self.assertEqual(self.calls, n)
        self.assertTrue(cache.pop_stale_events())

    def test_failure_without_stale_raises(self):
        @cache.ttl_cache("t_stale_b", 1, stale_ttl=1000, fail_cooldown=300)
        def f():
            self.calls += 1
            raise RuntimeError("down")

        with self.assertRaises(RuntimeError):
            f()
        with self.assertRaises(RuntimeError):
            f()
        self.assertEqual(self.calls, 1)


if __name__ == "__main__":
    unittest.main()
