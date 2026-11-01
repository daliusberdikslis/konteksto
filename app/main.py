"""Konteksto game API: on-demand games from a precomputed embedding matrix."""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .embeddings import EMBEDDINGS_DIR, EmbeddingStore, Game
from .lemmatize import lemmatize

MAX_GAMES = int(os.getenv("MAX_GAMES", "10000"))

store: EmbeddingStore | None = None
games: dict[str, "Game"] = {}


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


class SurrenderWord(BaseModel):
    lemma: str
    similarity: float
    rank: int


class SurrenderResponse(BaseModel):
    words: list[SurrenderWord]
    game_id: str


class HintResponse(BaseModel):
    lemma: str
    similarity: float
    rank: int
    game_id: str


@asynccontextmanager
async def lifespan(_: FastAPI):
    global store

    store = EmbeddingStore.load(EMBEDDINGS_DIR)
    print(f"[STATUS] Loaded {len(store.words)} embeddings from {EMBEDDINGS_DIR}")
    lemmatize("testas")  # pre-warm Hunspell dictionary (~10s first load)
    print("[STATUS] Hunspell dictionary ready")
    yield


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

    target_index: int | None = None
    if game_id is not None:
        game = games.get(game_id)
        # Stateless fallback: deterministic ids resolve without in-memory
        # state, so guesses survive restarts/redeploys and MAX_GAMES eviction.
        target_index = (
            game.target_index if game is not None else store.resolve_index(game_id)
        )
    if target_index is None:
        raise HTTPException(status_code=404, detail="Žaidimas nerastas.")

    resolved_lemma = lemmatize(clean_word)

    result = store.guess(target_index, resolved_lemma)
    if result is None:
        # Surface form may be in the vocab even when the lemma is not.
        result = store.guess(target_index, clean_word)
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
        game_id=game_id,
    )


@app.get("/api/v1/hint", response_model=HintResponse)
async def get_hint(
    game_id: str = Query(...),
    best_rank: int = Query(..., ge=2),
):
    """Reveal the word halfway between the target and the player's best rank.

    best_rank is supplied by the client (min position among guesses);
    the server re-derives nothing from guess history, keeping this stateless.
    """
    assert store is not None
    game = games.get(game_id)
    # Stateless fallback, same as guesses: deterministic ids resolve
    # without in-memory state.
    target_index = (
        game.target_index if game is not None else store.resolve_index(game_id)
    )
    if target_index is None:
        raise HTTPException(status_code=404, detail="Žaidimas nerastas.")
    if best_rank > len(store.words):
        raise HTTPException(status_code=400, detail="Neteisinga pozicija.")

    lemma, similarity, rank = store.hint(target_index, best_rank)

    return HintResponse(
        lemma=lemma,
        similarity=round(float(similarity), 5),
        rank=int(rank),
        game_id=game_id,
    )


@app.get("/api/v1/surrender", response_model=SurrenderResponse)
async def surrender(game_id: str = Query(...)):
    """Reveal the 10 closest words to the target, rank 1 first."""
    assert store is not None
    game = games.get(game_id)
    target_index = (
        game.target_index if game is not None else store.resolve_index(game_id)
    )
    if target_index is None:
        raise HTTPException(status_code=404, detail="Žaidimas nerastas.")
    words = [
        SurrenderWord(
            lemma=lemma,
            similarity=round(float(similarity), 5),
            rank=int(rank),
        )
        for lemma, similarity, rank in store.top_n(target_index, 10)
    ]
    return SurrenderResponse(words=words, game_id=game_id)
