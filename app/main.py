import gzip
import os
import shutil
from contextlib import asynccontextmanager
from pathlib import Path

import stanza
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from gensim.models import FastText

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
MODEL_BIN = ASSETS_DIR / "cc.lt.300.bin"
MODEL_GZ = ASSETS_DIR / "cc.lt.300.bin.gz"
TARGET_WORD_LEMMA = os.getenv("TARGET_WORD_LEMMA", "krepšinis")

nlp = None
model = None


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
    global nlp, model

    print("[STATUS] Booting Stanza Lithuanian pipeline...")
    stanza.download("lt", processors="tokenize,pos,lemma", verbose=False)
    nlp = stanza.Pipeline(
        "lt",
        processors="tokenize,pos,lemma",
        verbose=False,
    )

    model_path = ensure_model_decompressed()
    print(f"[STATUS] Loading fastText vectors from {model_path}...")
    model = FastText.load_fasttext_format(str(model_path))
    print(f"[STATUS] Engine ready. Target word lemma: {TARGET_WORD_LEMMA}")


@asynccontextmanager
async def lifespan(_: FastAPI):
    load_models()
    yield


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
    doc = nlp(word)
    if not doc.sentences or not doc.sentences[0].words:
        raise HTTPException(
            status_code=422,
            detail="Unable to parse input text morphology.",
        )
    return doc.sentences[0].words[0].lemma


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
