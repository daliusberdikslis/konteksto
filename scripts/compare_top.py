#!/usr/bin/env python3
"""Compare top-ranked neighbors for a target across embedding backends."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from fasttext_utils import (
    ensure_embedding_model,
    list_embedding_models,
    load_model,
    rank_words_by_target,
)

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_WORDS = ROOT / "assets" / "words" / "lt_nouns_100k.txt"


def load_word_sample(path: Path, limit: int) -> list[str]:
    words: list[str] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            w = line.strip().lower()
            if w:
                words.append(w)
            if len(words) >= limit:
                break
    return words


def print_top(label: str, ranked: list[tuple[str, float]], top_n: int) -> None:
    print(f"\n{label}")
    print("-" * len(label))
    for i, (word, sim) in enumerate(ranked[:top_n], start=1):
        print(f"{i:>3}. {word:<24} {sim:.5f}")


def load_game_top(path: Path, top_n: int) -> list[tuple[str, float]]:
    with open(path, encoding="utf-8") as f:
        payload = json.load(f)
    rankings = payload.get("rankings", {})
    rows = [
        (word, float(data["similarity"]))
        for word, data in rankings.items()
    ]
    rows.sort(key=lambda x: (-x[1], x[0]))
    return rows[:top_n]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare top semantic neighbors for a Konteksto target"
    )
    parser.add_argument("--target", required=True)
    parser.add_argument("--top", type=int, default=20)
    parser.add_argument(
        "--embedding-model",
        choices=list_embedding_models(),
        default="cc",
        help="Local fastText preset to score against the word list",
    )
    parser.add_argument("--model", type=Path, help="Explicit .bin path (overrides preset)")
    parser.add_argument("--download-model", action="store_true")
    parser.add_argument("--words", type=Path, default=DEFAULT_WORDS)
    parser.add_argument(
        "--game",
        type=Path,
        help="Optional precomputed game JSON to show stored rankings",
    )
    args = parser.parse_args()


    target = args.target.strip().lower()

    if args.game:
        print_top(f"Stored game ({args.game.name})", load_game_top(args.game, args.top), args.top)

    model_path, key, label = ensure_embedding_model(
        embedding_model=args.embedding_model,
        model_path=args.model,
        download=args.download_model,
    )
    print(f"Loading {label} from {model_path}...")
    model = load_model(model_path)
    words = load_word_sample(args.words, 100000)
    ranked = rank_words_by_target(model, target, words)
    print_top(f"{key}: {label}", ranked, args.top)



if __name__ == "__main__":
    main()
