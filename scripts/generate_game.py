#!/usr/bin/env python3
"""Precompute similarity rankings for a Konteksto target word."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from fasttext_utils import (
    DEFAULT_MODEL_BIN,
    DEFAULT_MODEL_GZ,
    cosine_similarity,
    ensure_fasttext_model,
    load_model,
    top_vocabulary,
)

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_WORDS = ROOT / "assets" / "words" / "lt_lemmas_100k.txt"
GAMES_DIR = ROOT / "games"

LT_WORD_RE = re.compile(r"^[a-ząčęėįšųūž\-]+$", re.IGNORECASE)


def load_word_list(path: Path) -> list[str]:
    words: list[str] = []
    seen: set[str] = set()
    with open(path, encoding="utf-8") as f:
        for line in f:
            w = line.strip().lower()
            if not w or w in seen:
                continue
            if not LT_WORD_RE.match(w) or len(w) < 2:
                continue
            seen.add(w)
            words.append(w)
    return words


def load_words_from_fasttext(model, top_k: int) -> list[str]:
    words: list[str] = []
    seen: set[str] = set()
    for token in top_vocabulary(model, top_k * 2):
        if len(words) >= top_k:
            break
        w = token.lower()
        if w in seen or len(w) < 2 or not LT_WORD_RE.match(w):
            continue
        seen.add(w)
        words.append(w)
    return words


def word_in_model(model, word: str) -> bool:
    try:
        model.get_word_vector(word)
        return True
    except ValueError:
        return False


def compute_rankings(model, target: str, words: list[str]) -> dict[str, dict]:
    target = target.strip().lower()
    if target not in words:
        words = [target] + [w for w in words if w != target]

    scored: list[tuple[str, float]] = []
    skipped = 0
    for word in words:
        if word == target:
            scored.append((word, 1.0))
            continue
        if not word_in_model(model, word) or not word_in_model(model, target):
            skipped += 1
            continue
        sim = cosine_similarity(model, word, target)
        scored.append((word, sim))

    if skipped:
        print(f"Skipped {skipped} words (no vector in fastText)")

    scored.sort(key=lambda x: (-x[1], x[0]))
    rankings: dict[str, dict] = {}
    for rank, (word, sim) in enumerate(scored, start=1):
        rankings[word] = {"rank": rank, "similarity": round(sim, 5)}
    return rankings


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Konteksto game rankings JSON")
    parser.add_argument("--target", required=True, help="Secret target word (lemma)")
    parser.add_argument("--words", type=Path, default=DEFAULT_WORDS)
    parser.add_argument(
        "--source",
        choices=["file", "fasttext"],
        default="file",
    )
    parser.add_argument("--top-k", type=int, default=100000)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL_BIN)
    parser.add_argument("--download-model", action="store_true")
    parser.add_argument("--output", type=Path, help="Output JSON path")
    args = parser.parse_args()

    target = args.target.strip().lower()
    output = args.output or (GAMES_DIR / f"{target}.json")

    model_path = ensure_fasttext_model(args.model, DEFAULT_MODEL_GZ, args.download_model)
    print(f"Loading fastText from {model_path}...")
    model = load_model(model_path)

    if args.source == "fasttext":
        print(f"Extracting top {args.top_k} words from fastText vocabulary...")
        words = load_words_from_fasttext(model, args.top_k)
    else:
        if not args.words.exists():
            raise FileNotFoundError(
                f"Word list not found: {args.words}. "
                "Run scripts/prepare_wordlist.py first or use --source fasttext."
            )
        words = load_word_list(args.words)
        print(f"Loaded {len(words)} words from {args.words}")

    print(f"Computing similarities against '{target}'...")
    rankings = compute_rankings(model, target, words)

    payload = {
        "meta": {
            "target": target,
            "total_words": len(rankings),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": args.source,
        },
        "rankings": rankings,
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))

    print(f"Wrote {len(rankings)} rankings to {output}")
    top5 = sorted(rankings.items(), key=lambda x: x[1]["rank"])[:5]
    print("Top 5:", [(w, d["similarity"]) for w, d in top5])


if __name__ == "__main__":
    main()
