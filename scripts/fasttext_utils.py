"""Shared fastText model loading and similarity helpers."""

from __future__ import annotations

import gzip
import shutil
from pathlib import Path

import fasttext
import numpy as np
import requests

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MODEL_BIN = ROOT / "assets" / "cc.lt.300.bin"
DEFAULT_MODEL_GZ = ROOT / "assets" / "cc.lt.300.bin.gz"
FASTTEXT_GZ_URL = (
    "https://dl.fbaipublicfiles.com/fasttext/vectors-crawl/cc.lt.300.bin.gz"
)


def ensure_fasttext_model(model_bin: Path, model_gz: Path, download: bool) -> Path:
    if model_bin.exists():
        return model_bin
    if model_gz.exists():
        print(f"Decompressing {model_gz}...")
        with gzip.open(model_gz, "rb") as src, open(model_bin, "wb") as dst:
            shutil.copyfileobj(src, dst)
        return model_bin
    if not download:
        raise FileNotFoundError(
            f"fastText model not found at {model_bin} or {model_gz}. "
            "Use --download-model or place the model under assets/."
        )
    model_gz.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading fastText model from {FASTTEXT_GZ_URL}...")
    with requests.get(FASTTEXT_GZ_URL, stream=True, timeout=600) as resp:
        resp.raise_for_status()
        with open(model_gz, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)
    return ensure_fasttext_model(model_bin, model_gz, download=False)


def load_model(model_bin: Path) -> fasttext.FastText._FastText:
    return fasttext.load_model(str(model_bin))


def cosine_similarity(model: fasttext.FastText._FastText, word_a: str, word_b: str) -> float:
    va = model.get_word_vector(word_a)
    vb = model.get_word_vector(word_b)
    na = np.linalg.norm(va)
    nb = np.linalg.norm(vb)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(va, vb) / (na * nb))


def cosine_similarities_to_target(
    model: fasttext.FastText._FastText,
    target: str,
    words: list[str],
) -> tuple[list[tuple[str, float]], int]:
    """Batch cosine similarity against one target word (numpy matrix multiply)."""
    try:
        target_vec = np.asarray(model.get_word_vector(target), dtype=np.float32)
    except ValueError:
        return [], len(words)

    target_norm = np.linalg.norm(target_vec)
    if target_norm == 0:
        return [], len(words)

    valid: list[str] = []
    rows: list[np.ndarray] = []
    skipped = 0
    for word in words:
        try:
            rows.append(np.asarray(model.get_word_vector(word), dtype=np.float32))
            valid.append(word)
        except ValueError:
            skipped += 1

    if not rows:
        return [], skipped

    matrix = np.stack(rows)
    norms = np.linalg.norm(matrix, axis=1)
    dots = matrix @ target_vec
    sims = np.divide(
        dots,
        norms * target_norm,
        out=np.zeros_like(dots),
        where=(norms > 0),
    )
    return [(w, float(s)) for w, s in zip(valid, sims)], skipped


def top_vocabulary(model: fasttext.FastText._FastText, top_k: int) -> list[str]:
    words, _freqs = model.get_words(include_freq=True)
    return [w.lower() for w in words[:top_k]]
