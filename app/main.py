"""Konteksto game API: on-demand games from a precomputed embedding matrix."""

import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .embeddings import EMBEDDINGS_DIR, EmbeddingStore, Game

LEGACY_GAMES_DIR = Path(__file__).resolve().parent.parent / "games"
LEGACY_TARGET = os.getenv("TARGET_WORD_LEMMA", "krepšinis")

LEX_URL = os.getenv("LEX_URL", "http://localhost:8080/")
MORPH_URL = os.getenv("MORPH_URL", "http://localhost:8090/morphology")
MAX_GAMES = int(os.getenv("MAX_GAMES", "10000"))

http_client: httpx.AsyncClient | None = None
store: EmbeddingStore | None = None
games: dict[str, "Game"] = {}


def _load_legacy_game(target: str) -> None:
    """Register a game pinned to the legacy precomputed target."""
    if store is None:
        return
    idx = store.index.get(target.strip().lower())
    if idx is None:
        return
    game = Game(id=secrets.token_urlsafe(16), target=store.words[idx], target_index=idx)
    games[game.id] = game


class NewGameResponse(BaseModel):
    game_id: str
    total_words: int


class GuessResponse(BaseModel):
    input: str
    lemma: str
    similarity: float
    rank: int
    game_id: str
    status: str = "success"


@asynccontextmanager
async def lifespan(_: FastAPI):
    global http_client, store

    http_client = httpx.AsyncClient(timeout=30.0)
    store = EmbeddingStore.load(EMBEDDINGS_DIR)
    _load_legacy_game(LEGACY_TARGET)
    print(f"[STATUS] Loaded {len(store.words)} embeddings from {EMBEDDINGS_DIR}")
    yield
    if http_client:
        await http_client.aclose()


app = FastAPI(
    title="Konteksto Game Engine API",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def lemmatize(word: str) -> str:
    """Lemmatize a single Lithuanian word using VDU lex + morph services."""
    assert http_client is not None
    rune_len = len(word)

    try:
        lex_resp = await http_client.post(LEX_URL, content=word)
        lex_resp.raise_for_status()
        lex_data = lex_resp.json()
    except (httpx.HTTPError, Exception):
        lex_data = {"seg": [[0, rune_len]], "s": [[0, rune_len]], "p": [[0, rune_len]]}

    morph_payload = {
        "scope": "all",
        "body": word,
        "annotations": {"lex": lex_data},
    }

    try:
        morph_resp = await http_client.post(MORPH_URL, json=morph_payload)
        morph_resp.raise_for_status()
        morph_data = morph_resp.json()
    except (httpx.HTTPError, Exception) as e:
        raise HTTPException(
            status_code=503,
            detail=f"Morphological analysis service unavailable: {e}",
        )

    msd = morph_data.get("msd", [])
    if not msd or not msd[0] or not msd[0][0] or len(msd[0][0]) < 1:
        raise HTTPException(
            status_code=422,
            detail="Unable to parse input text morphology.",
        )

    return msd[0][0][0]


@app.get("/")
async def root():
    return {"service": "konteksto", "status": "ok"}


@app.get("/health")
async def health():
    assert store is not None
    return {
        "status": "healthy",
        "total_words": len(store.words),
        "active_games": len(games),
    }


@app.post("/api/v1/games", response_model=NewGameResponse)
async def create_game():
    """Create a new game with a random secret word. O(1): just pick an index."""
    assert store is not None
    if len(games) >= MAX_GAMES:
        # Drop an arbitrary old game to bound memory.
        games.pop(next(iter(games)))
    game = store.random_game()
    games[game.id] = game
    return NewGameResponse(game_id=game.id, total_words=len(store.words))


@app.get("/api/v1/guess", response_model=GuessResponse)
async def process_user_guess(
    word: str = Query(..., min_length=1),
    game_id: str | None = Query(default=None),
):
    assert store is not None
    clean_word = word.strip().lower()
    if not clean_word:
        raise HTTPException(status_code=400, detail="Word parameter cannot be empty.")

    if game_id is not None:
        game = games.get(game_id)
        if game is None:
            raise HTTPException(status_code=404, detail="Žaidimas nerastas.")
    elif games:
        # Backwards compatibility: single-game clients guess against the
        # first registered game (legacy target when the vocab contains it).
        game = next(iter(games.values()))
    else:
        game = store.random_game()
        games[game.id] = game

    resolved_lemma = await lemmatize(clean_word)

    result = store.guess(game.target_index, resolved_lemma)
    if result is None:
        # Surface form may be in the vocab even when the lemma is not.
        result = store.guess(game.target_index, clean_word)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Žodis nerastas žodyne.",
        )

    similarity_score, rank = result

    return GuessResponse(
        input=word,
        lemma=resolved_lemma,
        similarity=round(float(similarity_score), 5),
        rank=int(rank),
        game_id=game.id,
    )
