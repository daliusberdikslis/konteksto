# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

People learning Lithuanian who play a semantic word-guessing game to build vocabulary. Sessions are casual: a few minutes a day or longer binge play, in the browser.

## Product Purpose

Konteksto is a Lithuanian semantic word-guessing game (in the Contexto/Semantle family): guess the secret word by semantic closeness, with rank feedback per guess, unlimited games, hints, and progress persistence. Success means learners keep playing and feel their Lithuanian vocabulary growing.

## Positioning

Lithuanian-first semantics: quality semantic similarity for Lithuanian via fastText embeddings plus lemmatization that handles inflections — something generic English-first guessing games cannot truthfully match.

## Operating Context

Single-game screen in the browser: guess input, ranked guess list with similarity feedback, hint button, new-game reset. Static frontend (`frontend/`) talks to a FastAPI backend (`app/`) serving precomputed embedding matrices; also deployable via Vercel (`frontend/vercel.json`, `frontend/api/`).

## Capabilities and Constraints

Confirmed: unlimited games, per-guess rank/similarity feedback, hints revealing a word between target and best rank, guess progress persisted in localStorage, Lithuanian-language UI.
Constraints: keep it minimal and fast — single screen, minimal UI, fast static frontend; no accounts, no social features planned. Daily-mode remains undecided.

## Brand Commitments

Name "Konteksto"; UI stays in Lithuanian. Existing game rules preserved.

## Evidence on Hand

Playable implementation: `frontend/index.html`, `frontend/app.js`, `frontend/style.css`; API in `app/main.py`, `app/embeddings.py`, `app/lemmatize.py`. No testimonials, benchmarks, or press to use — do not fabricate any.

## Product Principles

1. Learners first: every game element should teach Lithuanian, not just entertain.
2. Minimal and fast: one screen, instant feedback, no friction between guesses.
3. Honest Lithuanian semantics: inflections and lemmas must behave correctly for learners.
4. Free to replay: unlimited games and hints keep the learning loop open.
