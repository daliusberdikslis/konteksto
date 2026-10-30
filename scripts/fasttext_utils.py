"""Shared fastText model loading and similarity helpers."""

from __future__ import annotations

import gzip
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import fasttext
import numpy as np
import requests

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"

FASTTEXT_CC_GZ_URL = (
    "https://dl.fbaipublicfiles.com/fasttext/vectors-crawl/cc.lt.300.bin.gz"
)
FASTTEXT_WIKI_ZIP_URL = (
    "https://dl.fbaipublicfiles.com/fasttext/vectors-wiki/wiki.lt.zip"
)



@dataclass(frozen=True)
class FastTextModelSpec:
    key: str
    label: str
    bin_path: Path
    archive_path: Path | None = None
    url: str | None = None
    archive_member: str | None = None


EMBEDDING_MODELS: dict[str, FastTextModelSpec] = {
    "cc": FastTextModelSpec(
        key="cc",
        label="Facebook Common Crawl cc.lt.300",
        bin_path=ASSETS / "cc.lt.300.bin",
        archive_path=ASSETS / "cc.lt.300.bin.gz",
        url=FASTTEXT_CC_GZ_URL,
    ),
    "wiki": FastTextModelSpec(
        key="wiki",
        label="Facebook Wikipedia wiki.lt",
        bin_path=ASSETS / "wiki.lt.bin",
        archive_path=ASSETS / "wiki.lt.zip",
        url=FASTTEXT_WIKI_ZIP_URL,
        archive_member="wiki.lt.bin",
    ),
}

DEFAULT_MODEL_KEY = "cc"
DEFAULT_MODEL_BIN = EMBEDDING_MODELS[DEFAULT_MODEL_KEY].bin_path
DEFAULT_MODEL_GZ = EMBEDDING_MODELS[DEFAULT_MODEL_KEY].archive_path


def list_embedding_models() -> list[str]:
    return list(EMBEDDING_MODELS.keys())


def get_model_spec(key: str) -> FastTextModelSpec:
    spec = EMBEDDING_MODELS.get(key)
    if spec is None:
        choices = ", ".join(EMBEDDING_MODELS)
        raise ValueError(f"Unknown embedding model '{key}'. Choose one of: {choices}")
    return spec


def resolve_model_path(
    embedding_model: str | None = None,
    model_path: Path | None = None,
) -> tuple[Path, FastTextModelSpec | None]:
    """Resolve explicit path or preset key to a .bin file path."""
    if model_path is not None:
        return model_path.expanduser().resolve(), None
    key = embedding_model or DEFAULT_MODEL_KEY
    spec = get_model_spec(key)
    return spec.bin_path, spec


def _download_archive(url: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {url} -> {dest}")
    with requests.get(url, stream=True, timeout=600) as resp:
        resp.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)
    return dest


def _extract_gzip(archive: Path, dest_bin: Path) -> Path:
    print(f"Decompressing {archive}...")
    with gzip.open(archive, "rb") as src, open(dest_bin, "wb") as dst:
        shutil.copyfileobj(src, dst)
    return dest_bin


def _extract_zip_member(archive: Path, member: str, dest_bin: Path) -> Path:
    print(f"Extracting {member} from {archive}...")
    with zipfile.ZipFile(archive) as zf:
        with zf.open(member) as src, open(dest_bin, "wb") as dst:
            shutil.copyfileobj(src, dst)
    return dest_bin


def ensure_fasttext_model(
    model_bin: Path,
    model_archive: Path | None = None,
    download: bool = False,
    url: str | None = None,
    archive_member: str | None = None,
    help_text: str | None = None,
) -> Path:
    if model_bin.exists():
        return model_bin

    if model_archive and model_archive.exists():
        if model_archive.suffix == ".gz":
            return _extract_gzip(model_archive, model_bin)
        if model_archive.suffix == ".zip" and archive_member:
            return _extract_zip_member(model_archive, archive_member, model_bin)

    if not download:
        extra = f"\n{help_text}" if help_text else ""
        archive_hint = f" or {model_archive}" if model_archive else ""
        raise FileNotFoundError(
            f"fastText model not found at {model_bin}{archive_hint}. "
            f"Use --download-model or place the model under assets/.{extra}"
        )

    if not url or not model_archive:
        extra = f"\n{help_text}" if help_text else ""
        raise FileNotFoundError(
            f"No automatic download for {model_bin}.{extra}"
        )

    archive = _download_archive(url, model_archive)
    if archive.suffix == ".gz":
        return _extract_gzip(archive, model_bin)
    if archive.suffix == ".zip" and archive_member:
        return _extract_zip_member(archive, archive_member, model_bin)
    raise ValueError(f"Unsupported archive format: {archive}")


def ensure_embedding_model(
    embedding_model: str | None = None,
    model_path: Path | None = None,
    download: bool = False,
) -> tuple[Path, str, str]:
    """Return (bin path, model key, human label)."""
    path, spec = resolve_model_path(embedding_model, model_path)
    if spec is None:
        return path, "custom", str(path)

    resolved = ensure_fasttext_model(
        spec.bin_path,
        spec.archive_path,
        download=download,
        url=spec.url,
        archive_member=spec.archive_member,
    )
    return resolved, spec.key, spec.label


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


def rank_words_by_target(
    model: fasttext.FastText._FastText,
    target: str,
    words: list[str],
) -> list[tuple[str, float]]:
    """Rank lemmas by cosine similarity to target (target first at 1.0)."""
    target = target.strip().lower()
    others = [w for w in dict.fromkeys(words) if w != target]
    scored: list[tuple[str, float]] = [(target, 1.0)]
    batch, _ = cosine_similarities_to_target(model, target, others)
    scored.extend(batch)
    scored.sort(key=lambda x: (-x[1], x[0]))
    return scored
