"""VDU lex + morph lemmatization for offline scripts (same protocol as app/main.py)."""

from __future__ import annotations

import os
from typing import Optional

import httpx

DEFAULT_LEX_URL = os.getenv("LEX_URL", "http://localhost:8080/")
DEFAULT_MORPH_URL = os.getenv("MORPH_URL", "http://localhost:8090/morphology")


class VduLemmatizer:
    def __init__(
        self,
        lex_url: str = DEFAULT_LEX_URL,
        morph_url: str = DEFAULT_MORPH_URL,
        timeout: float = 30.0,
    ) -> None:
        self.lex_url = lex_url
        self.morph_url = morph_url
        self._client = httpx.Client(timeout=timeout)
        self._cache: dict[str, str] = {}

    def close(self) -> None:
        self._client.close()

    def is_available(self) -> bool:
        try:
            resp = self._client.post(self.lex_url, content="testas")
            return resp.status_code < 500
        except httpx.HTTPError:
            return False

    def lemmatize(self, word: str) -> Optional[str]:
        w = word.strip().lower()
        if not w:
            return None
        if w in self._cache:
            return self._cache[w]

        rune_len = len(w)
        try:
            lex_resp = self._client.post(self.lex_url, content=w)
            lex_resp.raise_for_status()
            lex_data = lex_resp.json()
        except httpx.HTTPError:
            lex_data = {
                "seg": [[0, rune_len]],
                "s": [[0, rune_len]],
                "p": [[0, rune_len]],
            }

        morph_payload = {
            "scope": "all",
            "body": w,
            "annotations": {"lex": lex_data},
        }
        try:
            morph_resp = self._client.post(self.morph_url, json=morph_payload)
            morph_resp.raise_for_status()
            morph_data = morph_resp.json()
        except httpx.HTTPError:
            return None

        msd = morph_data.get("msd", [])
        if not msd or not msd[0] or not msd[0][0] or len(msd[0][0]) < 1:
            return None

        lemma = msd[0][0][0].strip().lower()
        self._cache[w] = lemma
        return lemma

    def lemmatize_many(self, words: list[str], progress_every: int = 5000) -> list[str]:
        lemmas: list[str] = []
        seen: set[str] = set()
        for i, word in enumerate(words, start=1):
            if progress_every and i % progress_every == 0:
                print(f"  Lemmatized {i}/{len(words)} ({len(seen)} unique lemmas)...")
            lemma = self.lemmatize(word)
            if not lemma or lemma in seen:
                continue
            seen.add(lemma)
            lemmas.append(lemma)
        return lemmas
