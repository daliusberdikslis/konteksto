"""Lemma normalization for offline scripts (VDU preferred, Hunspell fallback)."""

from __future__ import annotations

from typing import Literal, Protocol

from hunspell_lemmatizer import HunspellLemmatizer
from vdu_morph import DEFAULT_LEX_URL, DEFAULT_MORPH_URL, VduLemmatizer

LemmatizerMode = Literal["auto", "vdu", "hunspell", "none"]


class Lemmatizer(Protocol):
    def lemmatize(self, word: str) -> str | None: ...
    def close(self) -> None: ...
    def is_available(self) -> bool: ...


def get_lemmatizer(
    mode: LemmatizerMode = "auto",
    lex_url: str | None = None,
    morph_url: str | None = None,
) -> Lemmatizer | None:
    if mode == "none":
        return None

    if mode == "hunspell":
        return HunspellLemmatizer()

    if mode == "vdu":
        lemmatizer = VduLemmatizer(
            lex_url=lex_url or DEFAULT_LEX_URL,
            morph_url=morph_url or DEFAULT_MORPH_URL,
        )
        if not lemmatizer.is_available():
            raise RuntimeError(
                "VDU lex/morph services are not reachable. "
                "Start morph+lex or use --lemmatizer hunspell."
            )
        return lemmatizer

    vdu = VduLemmatizer(
        lex_url=lex_url or DEFAULT_LEX_URL,
        morph_url=morph_url or DEFAULT_MORPH_URL,
    )
    if vdu.is_available():
        print("Using VDU lemmatizer (matches runtime API).")
        return vdu

    print("VDU not reachable — using Hunspell morphology dictionary.")
    vdu.close()
    return HunspellLemmatizer()
