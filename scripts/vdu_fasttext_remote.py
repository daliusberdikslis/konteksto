"""Query the public VDU social-media FastText demo (fasttext.vdu.lt)."""

from __future__ import annotations

import re
import urllib.parse
import urllib.request
from html import unescape

VDU_SEARCH_URL = "http://fasttext.vdu.lt/search"
_WORD_LINK_RE = re.compile(r"/search\?word=([^\"]+)")
_SCORE_RE = re.compile(r"<td>([0-9]+\.[0-9]+)</td>")


def fetch_neighbors(word: str, limit: int = 50) -> list[tuple[str, float]]:
    """Return nearest neighbors from the VDU demo site (HTML scrape)."""
    query = urllib.parse.urlencode({"word": word})
    url = f"{VDU_SEARCH_URL}?{query}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "konteksto-compare/1.0"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        html = resp.read().decode("utf-8", errors="replace")

    words = [
        urllib.parse.unquote(unescape(m.group(1)))
        for m in _WORD_LINK_RE.finditer(html)
    ]
    scores = [float(m.group(1)) for m in _SCORE_RE.finditer(html)]

    pairs: list[tuple[str, float]] = []
    for w, s in zip(words, scores):
        if w == word:
            continue
        pairs.append((w, s))
        if len(pairs) >= limit:
            break
    return pairs
