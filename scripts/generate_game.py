#!/usr/bin/env python3
"""Precompute similarity rankings for a Konteksto target word (lemma keys only)."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from fasttext_utils import (
    ensure_embedding_model,
    list_embedding_models,
    cosine_similarities_to_target,
    load_model,
    top_vocabulary,
)
from lemmatizer import Lemmatizer, LemmatizerMode, get_lemmatizer

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_WORDS = ROOT / "assets" / "words" / "lt_nouns_100k.txt"
GAMES_DIR = ROOT / "games"

LT_WORD_RE = re.compile(r"^[a-ząčęėįšųūž\-]+$", re.IGNORECASE)


def is_valid_word(word: str, min_len: int = 2) -> bool:
    w = word.strip().lower()
    return len(w) >= min_len and LT_WORD_RE.match(w) is not None and not w.isdigit()


def load_word_list(path: Path) -> list[str]:
    words: list[str] = []
    seen: set[str] = set()
    with open(path, encoding="utf-8") as f:
        for line in f:
            w = line.strip().lower()
            if not w or w in seen or not is_valid_word(w):
                continue
            seen.add(w)
            words.append(w)
    return words


def load_words_from_fasttext(model, top_k: int) -> list[str]:
    """Raw tokens from fastText vocabulary (may include inflected forms)."""
    words: list[str] = []
    seen: set[str] = set()
    for token in top_vocabulary(model, top_k * 3):
        if len(words) >= top_k:
            break
        w = token.lower()
        if w in seen or not is_valid_word(w):
            continue
        seen.add(w)
        words.append(w)
    return words


def normalize_to_lemmas(
    words: list[str],
    lemmatizer: Lemmatizer,
    top_k: int,
) -> list[str]:
    """Map surface forms to unique lemmas."""
    lemmas: list[str] = []
    seen: set[str] = set()
    for i, word in enumerate(words, start=1):
        if len(lemmas) >= top_k:
            break
        if i % 5000 == 0:
            print(f"  Lemmatizing {i}/{len(words)} ({len(lemmas)} lemmas so far)...")
        lemma = lemmatizer.lemmatize(word)
        if not lemma or not is_valid_word(lemma) or lemma in seen:
            continue
        seen.add(lemma)
        lemmas.append(lemma)
    return lemmas


def compute_rankings(model, target: str, lemmas: list[str]) -> dict[str, dict]:
    """Rank every word by cosine similarity to the target (Contexto-style)."""
    target = target.strip().lower()
    others = [w for w in dict.fromkeys(lemmas) if w != target]

    scored: list[tuple[str, float]] = [(target, 1.0)]
    batch, skipped = cosine_similarities_to_target(model, target, others)
    scored.extend(batch)

    if skipped:
        print(f"Skipped {skipped} lemmas (no vector in fastText)")

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
        help="Lemma file from prepare_wordlist.py (recommended) or raw fastText vocabulary",
    )
    parser.add_argument("--top-k", type=int, default=100000)
    parser.add_argument(
        "--embedding-model",
        choices=list_embedding_models(),
        default="cc",
        help="fastText preset: cc (Common Crawl), wiki, vdu-social",
    )
    parser.add_argument(
        "--model",
        type=Path,
        help="Explicit .bin path (overrides --embedding-model)",
    )
    parser.add_argument("--download-model", action="store_true")
    parser.add_argument("--output", type=Path, help="Output JSON path")
    parser.add_argument(
        "--lemmatizer",
        choices=["auto", "vdu", "hunspell", "none"],
        default="none",
        help="Lemma normalization (none for pre-built noun/lemma lists)",
    )
    parser.add_argument(
        "--no-lemmatize",
        action="store_true",
        help="Deprecated alias for --lemmatizer none",
    )
    parser.add_argument("--lex-url", default=None)
    parser.add_argument("--morph-url", default=None)
    args = parser.parse_args()

    target = args.target.strip().lower()
    output = args.output or (GAMES_DIR / f"{target}.json")
    lemmatizer_mode: LemmatizerMode = (
        "none" if args.no_lemmatize else args.lemmatizer
    )

    lemmatizer = get_lemmatizer(
        lemmatizer_mode,
        lex_url=args.lex_url,
        morph_url=args.morph_url,
    )
    lemmatize = lemmatizer is not None
    if lemmatize:
        print("Lemma-only rankings enabled.")
        target = lemmatizer.lemmatize(target) or target

    model_path, embedding_key, embedding_label = ensure_embedding_model(
        embedding_model=args.embedding_model,
        model_path=args.model,
        download=args.download_model,
    )
    print(f"Loading {embedding_label} from {model_path}...")
    model = load_model(model_path)

    if args.source == "fasttext":
        print(f"Extracting top {args.top_k} tokens from fastText vocabulary...")
        raw_words = load_words_from_fasttext(model, args.top_k * 3)
        if lemmatizer:
            print(f"Lemmatizing {len(raw_words)} tokens to unique lemmas...")
            lemmas = normalize_to_lemmas(raw_words, lemmatizer, args.top_k)
        else:
            lemmas = raw_words[:args.top_k]
    else:
        if not args.words.exists():
            raise FileNotFoundError(
                f"Word list not found: {args.words}. "
                "Run scripts/prepare_wordlist.py first or use --source fasttext."
            )
        raw_words = load_word_list(args.words)
        print(f"Loaded {len(raw_words)} entries from {args.words}")
        if lemmatizer:
            print("Normalizing word list to unique lemmas...")
            lemmas = normalize_to_lemmas(raw_words, lemmatizer, args.top_k)
        else:
            lemmas = raw_words[:args.top_k]

    print(f"Scoring {len(lemmas)} lemmas against '{target}'...")
    rankings = compute_rankings(model, target, lemmas)

    if lemmatizer:
        lemmatizer.close()

    payload = {
        "meta": {
            "target": target,
            "total_words": len(rankings),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": args.source,
            "word_list": (
                str(args.words.resolve().relative_to(ROOT))
                if args.source == "file"
                else None
            ),
            "lemma_only": lemmatize,
            "lemmatizer": lemmatizer_mode,
            "ranking_mode": "target_cosine",
            "embedding_model": embedding_key,
            "embedding_label": embedding_label,
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
