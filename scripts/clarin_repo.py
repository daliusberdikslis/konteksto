"""Download Lithuanian lexical resources from the CLARIN-LT repository."""

from __future__ import annotations

import json
import shutil
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CLARIN_DIR = ROOT / "assets" / "clarin"
CLARIN_API = "https://clarin-repo.lt/server/api/core/bitstreams/search/byItemHandle"

# https://clarin-repo.lt/items/5671f65b-bdc2-41d5-ad04-cc57004f3c3b
CCLL_FREQ_HANDLE = "20.500.11821/77"
CCLL_FREQ_ZIP = "LT_freq_lists.zip"
CCLL_LEMMA_MEMBER = "4-LT_lemma_alpha_freq_list.txt"

# https://clarin-repo.lt/items/2bf241af-42ab-4a68-8dd6-c119c2dd0e1e
UTKA_1M_HANDLE = "20.500.11821/12"
UTKA_1M_ZIP = "Lithuanian-wordlist.zip"
UTKA_DAZNINIS_MEMBER = "dazninis.txt"

# https://clarin-repo.lt/items/e61bfe1a-03a9-486a-bd5b-7d31d7102723
JCL_HANDLE = "20.500.11821/41"
JCL_ZIP = "JCL_Wordlist.zip"
JCL_LEMMA_MEMBER = "JCL_lemmas.txt"


def bitstream_content_url(handle: str, filename: str) -> str:
    query = f"{CLARIN_API}?handle={handle}&filename={filename}"
    req = urllib.request.Request(
        query,
        headers={"User-Agent": "konteksto-wordlist/1.0"},
    )
    with urllib.request.urlopen(req) as resp:
        data = json.load(resp)
    return data["_links"]["content"]["href"]


def download_file(url: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    print(f"Downloading {url} -> {dest}")
    req = urllib.request.Request(url, headers={"User-Agent": "konteksto-wordlist/1.0"})
    with urllib.request.urlopen(req) as resp, open(dest, "wb") as out:
        shutil.copyfileobj(resp, out)
    return dest


def download_clarin_zip(
    handle: str,
    filename: str,
    dest_dir: Path = DEFAULT_CLARIN_DIR,
) -> Path:
    dest = dest_dir / filename
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    url = bitstream_content_url(handle, filename)
    return download_file(url, dest)
