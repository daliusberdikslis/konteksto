import json
import os
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

GAMES_DIR = Path(__file__).resolve().parent.parent / "games"
TARGET_WORD_LEMMA = os.getenv("TARGET_WORD_LEMMA", "krepšinis")

LEX_URL = os.getenv("LEX_URL", "http://localhost:8080/")
MORPH_URL = os.getenv("MORPH_URL", "http://localhost:8090/morphology")

http_client = None
game_rankings: dict[str, dict] = {}
game_meta: dict = {}


def game_file_for_target(target: str) -> Path:
    return GAMES_DIR / f"{target.strip().lower()}.json"


def load_game_data(target: str) -> None:
    global game_rankings, game_meta

    path = game_file_for_target(target)
    if not path.exists():
        raise FileNotFoundError(
            f"Precomputed game file not found: {path}. "
            "Run scripts/generate_game.py --target <word> first."
        )

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    game_meta = data.get("meta", {})
    game_rankings = data.get("rankings", {})
    if not game_rankings:
        raise ValueError(f"Game file {path} has no rankings.")

    print(
        f"[STATUS] Loaded {len(game_rankings)} precomputed rankings "
        f"for target '{game_meta.get('target', target)}'"
    )


def wait_for_vdu_services() -> None:
    """Block until VDU lex and morph services are reachable."""
    import time

    for name, url in [("lex", LEX_URL), ("morph", MORPH_URL)]:
        for attempt in range(30):
            try:
                if name == "lex":
                    resp = http_client.post(url, content="testas")
                else:
                    payload = {
                        "scope": "all",
                        "body": "testas",
                        "annotations": {
                            "lex": {"seg": [[0, 6]], "s": [[0, 6]], "p": [[0, 6]]}
                        },
                    }
                    resp = http_client.post(url, json=payload)
                if resp.status_code < 500:
                    print(f"[STATUS] VDU {name} service ready")
                    break
            except httpx.ConnectError:
                pass
            time.sleep(1)
        else:
            print(f"[WARNING] VDU {name} service not reachable at {url}")


@asynccontextmanager
async def lifespan(_: FastAPI):
    global http_client

    http_client = httpx.Client(timeout=30.0)
    load_game_data(TARGET_WORD_LEMMA)
    yield
    if http_client:
        http_client.close()


app = FastAPI(
    title="Lithuanian Contexto Game Engine API",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def lemmatize(word: str) -> str:
    """Lemmatize a single Lithuanian word using VDU lex + morph services."""
    rune_len = len(word)

    try:
        lex_resp = http_client.post(LEX_URL, content=word)
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
        morph_resp = http_client.post(MORPH_URL, json=morph_payload)
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
    return {
        "status": "healthy",
        "target_lemma": TARGET_WORD_LEMMA,
        "total_words": len(game_rankings),
        "game_meta": game_meta,
    }


@app.get("/api/v1/guess")
async def process_user_guess(word: str = Query(..., min_length=1)):
    clean_word = word.strip().lower()
    if not clean_word:
        raise HTTPException(status_code=400, detail="Word parameter cannot be empty.")

    resolved_lemma = lemmatize(clean_word)

    entry = game_rankings.get(resolved_lemma)
    if not entry:
        raise HTTPException(
            status_code=404,
            detail="Žodis nerastas žodyne.",
        )

    similarity_score = float(entry["similarity"])

    return {
        "input": word,
        "lemma": resolved_lemma,
        "similarity": round(similarity_score, 5),
        "rank": int(entry["rank"]),
        "status": "success",
    }
