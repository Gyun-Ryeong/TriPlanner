"""
테스트는 .env에 진짜 키가 들어 있어도 외부 API를 절대 호출하지 않도록, 키를 비우고 캐시 위치를 임시 폴더로 돌립니다.
(config가 import되기 전에 실행되어야 해서 패키지 초기화에서 설정합니다)
"""
import os
import tempfile

os.environ["DEV_MODE"] = "on"  # 기존 테스트는 caveats/timings를 검증한다. 꺼진 경우는 별도 테스트에서 patch
os.environ["API_CACHE"] = "off"  # 테스트끼리 응답이 섞이지 않게
os.environ["PUBLIC_DATA_API_KEY"] = ""
os.environ["NAVER_CLIENT_ID"] = ""
os.environ["NAVER_CLIENT_SECRET"] = ""
_tmp = tempfile.mkdtemp(prefix="rag_test_")
os.environ["OVERVIEW_CACHE_PATH"] = os.path.join(_tmp, "overview.json")
os.environ["EMBED_CACHE_PATH"] = os.path.join(_tmp, "embed.npz")
os.environ["GAZETTEER_CACHE_PATH"] = os.path.join(_tmp, "gazetteer.json")
os.environ["LDONG_CACHE_PATH"] = os.path.join(_tmp, "ldong.json")
