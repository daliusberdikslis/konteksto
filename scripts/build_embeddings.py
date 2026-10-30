#!/usr/bin/env python3
"""Build a normalized embedding matrix for instant game generation.

Reads the curated lemma list, fetches one fastText vector per word,
L2-normalizes each row, and stores:
  <output-dir>/vocab.json   - word list + build metadata
  <output-dir>/matrix.npz   - float32 array "matrix" of shape (V, dim)

The backend loads these once at startup; a new game is then just a
random target index (~microseconds) and each guess is a single
matrix-vector multiply (~milliseconds for 40k x 300).

Example:
  python scripts/build_embeddings.py --download-model
  python scripts/build_embeddings.py --embedding-model wiki --top-k 50000
"""

from __future__ import annotations

import argparse
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from fasttext_utils import ensure_embedding_model, load_model

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_WORDS = ROOT / "assets" / "words" / "lt_nouns_100k.txt"
DEFAULT_OUTPUT_DIR = ROOT / "assets" / "embeddings"

LT_WORD_RE = re.compile(r"^[a-ząčęėįšųūž\-]+$", re.IGNORECASE)


def load_word_list(path: Path, top_k: int) -> list[str]:
    words: list[str] = []
    seen: set[str] = set()
    with open(path, encoding="utf-8") as f:
        for line in f:
            w = line.strip().lower()
            if len(w) >= 2 and LT_WORD_RE.match(w) and w not in seen:
                seen.add(w)
                words.append(w)
                if len(words) >= top_k:
                    break
    return words


def main() -> None:
    parser = argparse.ArgumentParser(description="Build normalized embedding matrix")
    parser.add_argument("--words", type=Path, default=DEFAULT_WORDS)
    parser.add_argument("--top-k", type=int, default=100000)
    parser.add_argument(
        "--embedding-model",
        choices=["cc", "wiki"],
        default="cc",
    )
    parser.add_argument("--model", type=Path, default=None)
    parser.add_argument("--download-model", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    model_path, embedding_key, embedding_label = ensure_embedding_model(
        embedding_model=args.embedding_model,
        model_path=args.model,
        download=args.download_model,
    )
    print(f"Loading {embedding_label} from {model_path}...")
    model = load_model(model_path)

    words = load_word_list(args.words, args.top_k)
    print(f"Loaded {len(words)} words from {args.words}")
    if not words:
        raise ValueError("Word list is empty.")

    t0 = time.perf_counter()
    rows: list[np.ndarray] = []
    for i, w in enumerate(words, start=1):
        try:
            vec = np.asarray(model.get_word_vector(w), dtype=np.float32)
        except ValueError:
            vec = np.zeros(model.get_dimension(), dtype=np.float32)
        norm = float(np.linalg.norm(vec))
        rows.append(vec / norm if norm > 0 else vec)
        if i % 10000 == 0:
            print(f"  embedded {i}/{len(words)}...")
    matrix = np.stack(rows).astype(np.float32)
    dt = time.perf_counter() - t0
    print(f"Embedded {len(words)} words in {dt:.1f}s")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(args.output_dir / "matrix.npz", matrix=matrix)
    with open(args.output_dir / "vocab.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "words": words,
                "dim": int(matrix.shape[1]),
                "total_words": len(words),
                "embedding_model": embedding_key,
                "embedding_label": embedding_label,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
            f,
            ensure_ascii=False,
        )

    size_mb = (args.output_dir / "matrix.npz").stat().st_size / 1e6
    print(f"Wrote {args.output_dir} (matrix.npz: {size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
