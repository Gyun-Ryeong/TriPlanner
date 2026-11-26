"""
기사 대표 사진 (원문 페이지의 og:image). 카카오톡에 링크를 붙이면 뜨는 미리보기 사진과 같은 것.

- 뉴스 API(네이버·연합뉴스)는 사진을 주지 않아서, 기사 원문 HTML 앞부분만 읽어 <meta property="og:image"> 를 찾는다.
- 미리보기 용도로만 쓴다: 화면에 작게, 원문 링크와 함께 보여준다 (사진을 저장하거나 키워 쓰지 않음).
- 같은 기사는 7일 동안 기억한다. 못 찾으면 image 가 빈 값.
- 안전: http/https 만, 내부 주소(localhost·사설 IP)는 열지 않는다. 앞 256KB만 읽고 4초 안에 끝낸다.
"""
import html
import ipaddress
import re
import socket
from urllib.parse import urljoin, urlparse

import requests

from collectors.cache import ttl_cache

MAX_BYTES = 256 * 1024
_META_RE = re.compile(r"<meta\b[^>]*>", re.I)
_ATTR_RE = re.compile(r'(\w[\w:-]*)\s*=\s*("([^"]*)"|\'([^\']*)\')', re.I)
_KEYS = ("og:image", "og:image:url", "twitter:image", "twitter:image:src")
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; TriPlannerBot/1.0; +link-preview)",
            "Accept": "text/html,application/xhtml+xml"}


def _public_host(url: str) -> bool:
    """내부망 주소로 요청이 가지 않게 (기사 링크가 이상해도 서버 안쪽을 열지 않도록)"""
    p = urlparse(url)
    if p.scheme not in ("http", "https") or not p.hostname:
        return False
    host = p.hostname
    if host in ("localhost",) or host.endswith(".local") or host.endswith(".internal"):
        return False
    try:
        addrs = {ai[4][0] for ai in socket.getaddrinfo(host, None)}
    except OSError:
        return False
    for a in addrs:
        ip = ipaddress.ip_address(a.split("%")[0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return False
    return True


def parse_og_image(page: str, base_url: str) -> str:
    """HTML 문자열에서 대표 사진 주소. og:image → twitter:image 순서. 없으면 ''."""
    found = {}
    for tag in _META_RE.findall(page):
        # _ATTR_RE: (이름, 따옴표 포함 값, "값", '값') → 큰따옴표면 셋째, 작은따옴표면 넷째
        attrs = {name.lower(): (dq if quoted.startswith('"') else sq) for name, quoted, dq, sq in _ATTR_RE.findall(tag)}
        key = (attrs.get("property") or attrs.get("name") or "").lower()
        if key in _KEYS and attrs.get("content") and key not in found:
            found[key] = attrs["content"].strip()
    for key in _KEYS:
        if found.get(key):
            url = urljoin(base_url, html.unescape(found[key]))
            if url.startswith(("http://", "https://")):
                return url
    return ""


@ttl_cache("ogimage", 7 * 24 * 3600)
def _fetch(url: str) -> dict:
    image = ""
    try:
        if _public_host(url):
            with requests.get(url, headers=_HEADERS, timeout=(3, 4), stream=True, allow_redirects=True) as r:
                if r.status_code < 400 and "html" in r.headers.get("content-type", "html"):
                    raw = b""
                    for chunk in r.iter_content(16384):
                        raw += chunk
                        if len(raw) >= MAX_BYTES or b"</head>" in raw.lower():
                            break
                    enc = r.encoding if r.encoding and r.encoding.lower() != "iso-8859-1" else "utf-8"
                    image = parse_og_image(raw.decode(enc, errors="ignore"), r.url)
    except requests.RequestException:
        pass
    return {"image": image}  # 빈 값도 dict 라 저장된다 (못 찾은 기사를 7일간 다시 열지 않음)


def og_image(url: str) -> str:
    if not url:
        return ""
    try:
        return _fetch(url)["image"]
    except Exception:
        return ""
