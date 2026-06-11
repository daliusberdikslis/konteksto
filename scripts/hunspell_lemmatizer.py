"""Offline Lithuanian lemmatization via Semantika Hunspell morphology dictionary."""

from __future__ import annotations

import urllib.request
from pathlib import Path
from typing import Optional

from spylls.hunspell import Dictionary

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_HUNSPELL_DIR = ROOT / "assets" / "hunspell" / "lt-LT_morphology"
HUNSPELL_BASE_URL = (
    "https://raw.githubusercontent.com/Semantika2/"
    "Hunspell-Zodynai-ir-gramatika-v.45/master"
)


def ensure_hunspell_dictionary(dict_dir: Path = DEFAULT_HUNSPELL_DIR) -> Path:
    aff = dict_dir.parent / f"{dict_dir.name}.aff"
    dic = dict_dir.parent / f"{dict_dir.name}.dic"
    if aff.exists() and dic.exists():
        return dict_dir
    dict_dir.parent.mkdir(parents=True, exist_ok=True)
    for ext in (".aff", ".dic"):
        url = f"{HUNSPELL_BASE_URL}/{dict_dir.name}{ext}"
        dest = dict_dir.parent / f"{dict_dir.name}{ext}"
        print(f"Downloading {url}...")
        urllib.request.urlretrieve(url, dest)
    return dict_dir


class HunspellLemmatizer:
    def __init__(self, dict_dir: Path = DEFAULT_HUNSPELL_DIR) -> None:
        path = ensure_hunspell_dictionary(dict_dir)
        self._dict = Dictionary.from_files(str(path))
        self._cache: dict[str, str] = {}

    def close(self) -> None:
        return None

    def is_available(self) -> bool:
        return True

    def lemmatize(self, word: str) -> Optional[str]:
        w = word.strip().lower()
        if not w:
            return None
        if w in self._cache:
            return self._cache[w]

        for form in self._dict.lookuper.good_forms(w):
            lemma = form.stem.strip().lower()
            self._cache[w] = lemma
            return lemma

        self._cache[w] = w
        return w
