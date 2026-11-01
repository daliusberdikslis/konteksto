"""Vocabulary + normalized embedding matrix for instant game generation."""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

EMBEDDINGS_DIR = Path(__file__).resolve().parent.parent / "assets" / "embeddings"

# Salt binds a game_id to one vocab entry. It is a constant (not a secret):
# forging another valid game_id only selects a different target word,
# which gives no advantage. Changing it invalidates all existing game_ids.
GAME_ID_SALT = "konteksto-v1"


@dataclass
class Game:
    id: str
    target: str
    target_index: int


@dataclass
class EmbeddingStore:
    """Precomputed vocabulary with L2-normalized vectors.

    Cosine similarity between any two words is a single dot product,
    so ranking guesses for a random target needs no per-game precompute:
    each guess is one matrix-vector multiply (~ms for 40k x 300).
    """

    words: list[str]
    matrix: np.ndarray  # (V, dim), rows L2-normalized
    index: dict[str, int] = field(init=False)

    def __post_init__(self) -> None:
        self.index = {w: i for i, w in enumerate(self.words)}

    @classmethod
    def load(cls, directory: Path = EMBEDDINGS_DIR) -> EmbeddingStore:
        with open(directory / "vocab.json", encoding="utf-8") as f:
            vocab = json.load(f)
        data = np.load(directory / "matrix.npz")
        matrix = np.asarray(data["matrix"], dtype=np.float32)
        words = list(vocab["words"])
        if matrix.shape[0] != len(words):
            raise ValueError(
                f"Embedding matrix has {matrix.shape[0]} rows "
                f"but vocab has {len(words)} words."
            )
        return cls(words=words, matrix=matrix)

    def game_id_for_index(self, idx: int) -> str:
        """Deterministic, restart-proof game id for a vocab index.

        Same index + same vocab always yields the same id, so the server
        can resolve it without in-memory state (survives restarts/deploys).
        """
        word = self.words[idx]
        digest = hashlib.sha256(
            f"{GAME_ID_SALT}:{idx}:{word}".encode("utf-8")
        ).hexdigest()[:12]
        return f"{idx}-{digest}"

    def resolve_index(self, game_id: str) -> int | None:
        """Recover the target index from a deterministic game id, or None."""
        try:
            idx_str, digest = game_id.split("-", 1)
            idx = int(idx_str)
        except (ValueError, AttributeError):
            return None
        if not 0 <= idx < len(self.words):
            return None
        expected = hashlib.sha256(
            f"{GAME_ID_SALT}:{idx}:{self.words[idx]}".encode("utf-8")
        ).hexdigest()[:12]
        if not hmac.compare_digest(expected, digest.lower()):
            return None
        return idx

    def random_game(self) -> Game:
        idx = secrets.randbelow(len(self.words))
        return Game(
            id=self.game_id_for_index(idx),
            target=self.words[idx],
            target_index=idx,
        )

    def guess(self, target_index: int, lemma: str) -> tuple[float, int] | None:
        """Return (similarity, rank) of lemma against the target word.

        Rank is 1-based: 1 + number of vocab words strictly more similar
        to the target than the guess.
        """
        guess_index = self.index.get(lemma)
        if guess_index is None:
            return None
        target_vec = self.matrix[target_index]
        sims = self.matrix @ target_vec
        similarity = float(sims[guess_index])
        rank = int(np.count_nonzero(sims > sims[guess_index])) + 1
        return similarity, rank

    def hint(self, target_index: int, best_rank: int) -> tuple[str, float, int]:
        """Return the word halfway between the target (rank 1) and best_rank.

        Picks the word at sorted position ceil(best_rank / 2) in
        descending-similarity order, with its true similarity and rank.
        Ties are stepped over toward the target so the result is always
        strictly better than best_rank (for best_rank >= 2), and therefore
        can never duplicate an existing guess.
        """
        if best_rank < 2:
            raise ValueError("best_rank must be at least 2.")
        target_vec = self.matrix[target_index]
        sims = self.matrix @ target_vec
        order = np.argsort(-sims, kind="stable")
        idx = (best_rank - 1) // 2
        if idx >= len(self.words):
            idx = len(self.words) - 1
        # Walk toward the target past similarity ties: with ties, the word
        # at `idx` can share best_rank's similarity tier, which would show
        # the same rank number and could repeat a guessed word. Rank 1 is
        # always strictly better (best_rank >= 2), so this terminates.
        while idx > 0:
            word_idx = int(order[idx])
            rank = int(np.count_nonzero(sims > sims[word_idx])) + 1
            if rank < best_rank:
                break
            idx -= 1
        word_idx = int(order[idx])
        similarity = float(sims[word_idx])
        rank = int(np.count_nonzero(sims > sims[word_idx])) + 1
        return self.words[word_idx], similarity, rank
