"""In-process Lithuanian lemmatization: VDU services when reachable, Hunspell fallback."""

from __future__ import annotations

import os
import urllib.request
from pathlib import Path

import httpx
from spylls.hunspell import Dictionary

ROOT = Path(__file__).resolve().parent.parent
HUNSPELL_DIR = ROOT / "assets" / "hunspell" / "lt-LT_morphology"
HUNSPELL_BASE_URL = (
    "https://raw.githubusercontent.com/Semantika2/"
    "Hunspell-Zodynai-ir-gramatika-v.45/master"
)

LEX_URL = os.getenv("LEX_URL", "http://localhost:8080/")
MORPH_URL = os.getenv("MORPH_URL", "http://localhost:8090/morphology")

_hunspell: Dictionary | None = None
_use_vdu: bool | None = None


def _download_hunspell(aff: Path, dic: Path) -> None:
    aff.parent.mkdir(parents=True, exist_ok=True)
    for dest in (aff, dic):
        print(f"[STATUS] Downloading {dest.name}...")
        urllib.request.urlretrieve(f"{HUNSPELL_BASE_URL}/{dest.name}", dest)


def _hunspell_dict() -> Dictionary:
    global _hunspell
    if _hunspell is None:
        aff = HUNSPELL_DIR.parent / f"{HUNSPELL_DIR.name}.aff"
        dic = HUNSPELL_DIR.parent / f"{HUNSPELL_DIR.name}.dic"
        if not (aff.exists() and dic.exists()):
            _download_hunspell(aff, dic)
        _hunspell = Dictionary.from_files(str(HUNSPELL_DIR))
    return _hunspell


def hunspell_lemmatize(word: str) -> str:
    """Best-effort lemma from the Semantika Hunspell morphology dictionary."""
    w = word.strip().lower()
    if not w:
        return w
    for form in _hunspell_dict().lookuper.good_forms(w):
        stem = form.stem.strip().lower()
        if stem:
            return stem
    return w


async def _vdu_lemmatize(client: httpx.AsyncClient, word: str) -> str | None:
    rune_len = len(word)
    try:
        lex_resp = await client.post(LEX_URL, content=word)
        lex_resp.raise_for_status()
        lex_data = lex_resp.json()
    except (httpx.HTTPError, Exception):
        lex_data = {"seg": [[0, rune_len]], "s": [[0, rune_len]], "p": [[0, rune_len]]}
    try:
        morph_resp = await client.post(
            MORPH_URL,
            json={"scope": "all", "body": word, "annotations": {"lex": lex_data}},
        )
        morph_resp.raise_for_status()
        msd = morph_resp.json().get("msd", [])
    except (httpx.HTTPError, Exception):
        return None
    if not msd or not msd[0] or not msd[0][0] or len(msd[0][0]) < 1:
        return None
    return msd[0][0][0]


async def probe_vdu(client: httpx.AsyncClient) -> bool:
    """Check once at startup whether VDU lex/morph services are reachable."""
    try:
        resp = await client.post(LEX_URL, content="testas")
        return resp.status_code < 500
    except (httpx.HTTPError, Exception):
        return False


async def lemmatize(client: httpx.AsyncClient, word: str) -> str:
    """Lemmatize via VDU when available, otherwise Hunspell. Never raises."""
    global _use_vdu
    w = word.strip().lower()
    if _use_vdu is None:
        _use_vdu = await probe_vdu(client)
        print(f"[STATUS] VDU lemmatizer reachable: {_use_vdu}")
    if _use_vdu:
        lemma = await _vdu_lemmatize(client, w)
        if lemma:
            return lemma
    return hunspell_lemmatize(w)
