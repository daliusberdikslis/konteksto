import gzip
import os
import shutil
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from gensim.models import FastText

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
MODEL_BIN = ASSETS_DIR / "cc.lt.300.bin"
MODEL_GZ = ASSETS_DIR / "cc.lt.300.bin.gz"
TARGET_WORD_LEMMA = os.getenv("TARGET_WORD_LEMMA", "krepšinis")

LEX_URL = os.getenv("LEX_URL", "http://localhost:8080/")
MORPH_URL = os.getenv("MORPH_URL", "http://localhost:8090/morphology")

model = None
http_client = None


def ensure_model_decompressed() -> Path:
    if MODEL_BIN.exists():
        return MODEL_BIN
    if not MODEL_GZ.exists():
        raise FileNotFoundError(
            f"fastText model not found. Expected {MODEL_BIN} or {MODEL_GZ}."
        )
    print(f"[STATUS] Decompressing {MODEL_GZ.name} (~4.2 GB)...")
    with gzip.open(MODEL_GZ, "rb") as src, open(MODEL_BIN, "wb") as dst:
        shutil.copyfileobj(src, dst)
    print(f"[STATUS] Decompressed model written to {MODEL_BIN}")
    return MODEL_BIN


def load_models() -> None:
    global model, http_client

    http_client = httpx.Client(timeout=30.0)

    model_path = ensure_model_decompressed()
    print(f"[STATUS] Loading fastText vectors from {model_path}...")
    model = FastText.load_fasttext_format(str(model_path))
    print(f"[STATUS] Engine ready. Target word lemma: {TARGET_WORD_LEMMA}")


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
    load_models()
    wait_for_vdu_services()
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

    # Step 1: Get segmentation from lex service
    try:
        lex_resp = http_client.post(LEX_URL, content=word)
        lex_resp.raise_for_status()
        lex_data = lex_resp.json()
    except (httpx.HTTPError, Exception):
        # Fallback: create manual segmentation for a single word
        lex_data = {"seg": [[0, rune_len]], "s": [[0, rune_len]], "p": [[0, rune_len]]}

    # Step 2: Call morph service with text + segmentation
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

    # Step 3: Extract lemma from morph response
    # Response format: {"msd": [[["lemma", "mi_tag"], ...], ...], "stem": [...]}
    msd = morph_data.get("msd", [])
    if not msd or not msd[0] or not msd[0][0] or len(msd[0][0]) < 1:
        raise HTTPException(
            status_code=422,
            detail="Unable to parse input text morphology.",
        )

    lemma = msd[0][0][0]
    return lemma


@app.get("/")
async def root():
    return {"service": "konteksto", "status": "ok"}


@app.get("/health")
async def health():
    return {"status": "healthy", "target_lemma": TARGET_WORD_LEMMA}


@app.get("/api/v1/guess")
async def process_user_guess(word: str = Query(..., min_length=1)):
    clean_word = word.strip().lower()
    if not clean_word:
        raise HTTPException(status_code=400, detail="Word parameter cannot be empty.")

    resolved_lemma = lemmatize(clean_word)

    try:
        similarity_score = float(model.wv.similarity(resolved_lemma, TARGET_WORD_LEMMA))
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail="Žodis nerastas duomenų bazėje.",
        )

    return {
        "input": word,
        "lemma": resolved_lemma,
        "similarity": round(similarity_score, 5),
        "status": "success",
    }
