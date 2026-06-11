#!/usr/bin/env python3
"""Build a curated Lithuanian lemma word list for Konteksto game generation."""

from __future__ import annotations

import argparse
import re
import shutil
import zipfile
from pathlib import Path

from fasttext_utils import (
    DEFAULT_MODEL_BIN,
    DEFAULT_MODEL_GZ,
    ensure_fasttext_model,
    load_model,
    top_vocabulary,
)

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = ROOT / "assets" / "words" / "lt_lemmas_100k.txt"

CONTENT_POS_PREFIXES = ("dkt", "dktv", "bdv", "v", "adv", "N", "A", "V", "R")
LT_WORD_RE = re.compile(r"^[a-ząčęėįšųūž\-]+$", re.IGNORECASE)


def is_valid_lemma(word: str, min_len: int = 2) -> bool:
    w = word.strip().lower()
    if len(w) < min_len:
        return False
    if not LT_WORD_RE.match(w):
        return False
    if w.isdigit():
        return False
    return True


def load_lemmas_from_ccll_file(path: Path) -> list[tuple[str, int]]:
    entries: list[tuple[str, int]] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) < 2:
                parts = line.split()
            if len(parts) < 2:
                continue
            lemma = parts[0].strip().lower()
            try:
                freq = int(parts[1].replace(",", ""))
            except ValueError:
                continue
            if is_valid_lemma(lemma):
                entries.append((lemma, freq))
    entries.sort(key=lambda x: -x[1])
    return entries


def load_lemmas_from_utka_zip(zip_path: Path) -> list[tuple[str, int]]:
    entries: list[tuple[str, int]] = []
    with zipfile.ZipFile(zip_path) as zf:
        txt_name = next(
            (n for n in zf.namelist() if n.endswith("dazninis.txt") or n.endswith(".txt")),
            None,
        )
        if not txt_name:
            raise ValueError(f"No .txt found inside {zip_path}")
        with zf.open(txt_name) as raw:
            for line in raw:
                line = line.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                parts = line.split("\t")
                if len(parts) < 4:
                    continue
                headword, pos = parts[0].strip().lower(), parts[1].strip().lower()
                try:
                    freq = int(parts[3].replace(",", ""))
                except ValueError:
                    continue
                if not is_valid_lemma(headword):
                    continue
                if pos and not any(pos.startswith(p) for p in CONTENT_POS_PREFIXES):
                    continue
                entries.append((headword, freq))
    merged: dict[str, int] = {}
    for lemma, freq in entries:
        merged[lemma] = max(merged.get(lemma, 0), freq)
    return sorted(merged.items(), key=lambda x: -x[1])


def extract_zip_member(zip_path: Path, member_suffix: str, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        name = next((n for n in zf.namelist() if n.endswith(member_suffix)), None)
        if not name:
            raise ValueError(f"No file ending with {member_suffix} in {zip_path}")
        out = dest_dir / Path(name).name
        with zf.open(name) as src, open(out, "wb") as dst:
            shutil.copyfileobj(src, dst)
        return out


def load_from_dlkt(
    ccll_zip: Path | None,
    utka_zip: Path | None,
    lemma_file: Path | None,
) -> list[str]:
    lemmas: list[str] = []
    seen: set[str] = set()

    if lemma_file and lemma_file.exists():
        for lemma, _ in load_lemmas_from_ccll_file(lemma_file):
            if lemma not in seen:
                seen.add(lemma)
                lemmas.append(lemma)

    if ccll_zip and ccll_zip.exists():
        tmp = ccll_zip.parent / "_ccll_extract"
        try:
            extracted = extract_zip_member(
                ccll_zip, "LT_lemma_alpha_freq_list.txt", tmp
            )
            for lemma, _ in load_lemmas_from_ccll_file(extracted):
                if lemma not in seen:
                    seen.add(lemma)
                    lemmas.append(lemma)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    if utka_zip and utka_zip.exists():
        for lemma, _ in load_lemmas_from_utka_zip(utka_zip):
            if lemma not in seen:
                seen.add(lemma)
                lemmas.append(lemma)

    return lemmas


def fill_from_fasttext(model, seen: set[str], top_k: int) -> list[str]:
    added: list[str] = []
    for token in top_vocabulary(model, top_k * 2):
        if len(added) + len(seen) >= top_k:
            break
        w = token.lower()
        if w in seen or not is_valid_lemma(w):
            continue
        seen.add(w)
        added.append(w)
    return added


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare Lithuanian lemma word list")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--top-k", type=int, default=100000)
    parser.add_argument("--ccll-zip", type=Path, help="CCLL LT_freq_lists.zip")
    parser.add_argument("--utka-zip", type=Path, help="Lithuanian-wordlist.zip (1M corpus)")
    parser.add_argument("--lemma-file", type=Path, help="LT_lemma_alpha_freq_list.txt")
    parser.add_argument(
        "--source",
        choices=["dlkt", "fasttext", "both"],
        default="both",
    )
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL_BIN)
    parser.add_argument("--download-model", action="store_true")
    args = parser.parse_args()

    lemmas: list[str] = []
    seen: set[str] = set()

    if args.source in ("dlkt", "both"):
        dlkt = load_from_dlkt(args.ccll_zip, args.utka_zip, args.lemma_file)
        for lemma in dlkt:
            if lemma not in seen:
                seen.add(lemma)
                lemmas.append(lemma)
        print(f"DLKT sources: {len(lemmas)} unique lemmas")

    if args.source in ("fasttext", "both") or len(lemmas) < args.top_k:
        model_path = ensure_fasttext_model(
            args.model, DEFAULT_MODEL_GZ, args.download_model
        )
        print(f"Loading fastText from {model_path}...")
        model = load_model(model_path)
        if len(lemmas) < args.top_k:
            fill = fill_from_fasttext(model, seen, args.top_k)
            lemmas.extend(fill)
            print(f"fastText fill: {len(fill)} lemmas")

    if args.source == "fasttext" and not lemmas:
        model_path = ensure_fasttext_model(
            args.model, DEFAULT_MODEL_GZ, args.download_model
        )
        model = load_model(model_path)
        lemmas = fill_from_fasttext(model, set(), args.top_k)

    final = lemmas[:args.top_k]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        for w in final:
            f.write(w + "\n")

    print(f"Wrote {len(final)} lemmas to {args.output}")


if __name__ == "__main__":
    main()
