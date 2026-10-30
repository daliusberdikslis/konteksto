"""In-process Lithuanian lemmatization via Hunspell morphology dictionary."""

from __future__ import annotations

import urllib.request
from pathlib import Path

from spylls.hunspell import Dictionary

ROOT = Path(__file__).resolve().parent.parent
HUNSPELL_DIR = ROOT / "assets" / "hunspell" / "lt-LT_morphology"
HUNSPELL_BASE_URL = (
    "https://raw.githubusercontent.com/Semantika2/"
    "Hunspell-Zodynai-ir-gramatika-v.45/master"
)

_hunspell: Dictionary | None = None


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


def lemmatize(word: str) -> str:
    """Best-effort lemma from the Semantika Hunspell morphology dictionary."""
    w = word.strip().lower()
    if not w:
        return w
    for form in _hunspell_dict().lookuper.good_forms(w):
        stem = form.stem.strip().lower()
        if stem:
            return stem
    return w
