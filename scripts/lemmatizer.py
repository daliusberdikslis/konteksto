"""Lemma normalization for offline scripts (Hunspell morphology dictionary)."""

from __future__ import annotations

from typing import Literal, Protocol

from hunspell_lemmatizer import HunspellLemmatizer

LemmatizerMode = Literal["hunspell", "none"]


class Lemmatizer(Protocol):
    def lemmatize(self, word: str) -> str | None: ...
    def close(self) -> None: ...
    def is_available(self) -> bool: ...


def get_lemmatizer(mode: LemmatizerMode = "hunspell") -> Lemmatizer | None:
    if mode == "none":
        return None
    return HunspellLemmatizer()
