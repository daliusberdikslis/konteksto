// ============================================================
// KONTEKSTO — Game Engine (Frontend)
// ============================================================

const PROD_API_BASE = "https://daliusber-konteksto.hf.space";

function resolveApiBase() {
  // Local static server: talk to the local backend directly (no token needed).
  // `?api=<url>` overrides outright; `?api=direct` forces production backend.
  // Production: call the HF Space backend directly.
  try {
    const params = new URLSearchParams(window.location.search);
    const override = params.get("api");
    if (override === "direct") return PROD_API_BASE;
    if (override) return override.replace(/\/+$/, "");
    const h = window.location.hostname;
    if (!h || h === "localhost" || h === "127.0.0.1") return "http://127.0.0.1:8000";
  } catch {
    // ignore — fall through to prod
  }
  return PROD_API_BASE;
}

const CONFIG = {
  API_BASE: resolveApiBase(),
  GUESS_ENDPOINT: "/api/v1/guess",
  NEW_GAME_ENDPOINT: "/api/v1/games",
  HINT_ENDPOINT: "/api/v1/hint",
  SURRENDER_ENDPOINT: "/api/v1/surrender",
  HEALTH_ENDPOINT: "/health",
  WIN_THRESHOLD: 0.9999,
  REQUEST_TIMEOUT_MS: 120_000,
  MAX_ATTEMPTS: 6,
  RETRY_DELAY_MS: 8_000,
  STORAGE_VERSION: 4,
};

// --- State ---
const state = {
  gameId: null,
  guesses: [],
  isLoading: false,
  hasWon: false,
  hasSurrendered: false,
  totalWords: null,
};

// --- DOM References ---
const dom = {
  form: document.getElementById("guess-form"),
  input: document.getElementById("guess-input"),
  submit: document.getElementById("guess-submit"),
  error: document.getElementById("input-error"),
  guessList: document.getElementById("guess-list"),
  winBanner: document.getElementById("win-banner"),
  winCount: document.getElementById("win-count"),
  resetBtn: document.getElementById("reset-game"),
  hintBtn: document.getElementById("hint-btn"),
  surrenderBtn: document.getElementById("surrender-btn"),
  meta: document.getElementById("game-meta"),
};

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

const CURRENT_GAME_KEY = `konteksto:v${CONFIG.STORAGE_VERSION}:current-game`;

function storageKey() {
  return state.gameId
    ? `konteksto:v${CONFIG.STORAGE_VERSION}:${state.gameId}`
    : CURRENT_GAME_KEY;
}

// --- Progress persistence ---
function saveProgress() {
  try {
    const payload = {
      version: CONFIG.STORAGE_VERSION,
      gameId: state.gameId,
      totalWords: state.totalWords,
      guesses: state.guesses,
      hasWon: state.hasWon,
      hasSurrendered: state.hasSurrendered,
      savedAt: new Date().toISOString(),
    };
    localStorage.setItem(storageKey(), JSON.stringify(payload));
    if (state.gameId) {
      localStorage.setItem(CURRENT_GAME_KEY, state.gameId);
    }
  } catch (err) {
    console.warn("Could not save progress:", err);
  }
}

function loadProgress() {
  try {
    let raw = state.gameId ? localStorage.getItem(storageKey()) : null;
    if (!raw) {
      const currentId = localStorage.getItem(CURRENT_GAME_KEY);
      if (currentId) {
        state.gameId = currentId;
        raw = localStorage.getItem(storageKey());
      }
    }
    if (!raw) return false;

    const data = JSON.parse(raw);
    if (
      data.version !== CONFIG.STORAGE_VERSION ||
      data.gameId !== state.gameId ||
      !Array.isArray(data.guesses)
    ) {
      localStorage.removeItem(storageKey());
      return false;
    }

    state.guesses = data.guesses.filter(
      (g) =>
        g &&
        typeof g.input === "string" &&
        typeof g.lemma === "string" &&
        typeof g.similarity === "number" &&
        typeof g.position === "number"
    );
    state.hasWon = Boolean(data.hasWon);
    state.hasSurrendered = Boolean(data.hasSurrendered);
    if (typeof data.totalWords === "number" && data.totalWords > 0) {
      state.totalWords = data.totalWords;
    }
    return true;
  } catch (err) {
    console.warn("Could not load progress:", err);
    localStorage.removeItem(storageKey());
    return false;
  }
}

function clearProgress() {
  try {
    localStorage.removeItem(storageKey());
    if (state.gameId) {
      try {
        if (localStorage.getItem(CURRENT_GAME_KEY) === state.gameId) {
          localStorage.removeItem(CURRENT_GAME_KEY);
        }
      } catch (err) {
        localStorage.removeItem(CURRENT_GAME_KEY);
      }
    }
  } catch (err) {
    console.warn("Could not clear progress:", err);
  }
}

function isLegacyGameId(id) {
  // Random ids from before deterministic game ids can never resolve
  // after a backend restart — treat them as dead and start fresh.
  return typeof id !== "string" || !/^\d+-[0-9a-f]{12}$/i.test(id);
}

function isGameNotFound(err) {
  return Boolean(err && typeof err.message === "string" && err.message.includes("Žaidimas nerastas"));
}

function isWordNotFound(err) {
  return Boolean(err && typeof err.message === "string" && err.message.includes("Žodis nerastas"));
}
 // --- API ---
 async function fetchHealth() {
   const url = `${CONFIG.API_BASE}${CONFIG.HEALTH_ENDPOINT}`;
   try {
     const response = await fetch(url);
     if (!response.ok) return null;
     return response.json();
   } catch {
     return null;
   }
 }

async function fetchNewGame() {
  const url = `${CONFIG.API_BASE}${CONFIG.NEW_GAME_ENDPOINT}`;
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), CONFIG.REQUEST_TIMEOUT_MS);
  try {
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
      signal: controller.signal,
    });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(body.detail || `Serverio klaida (${response.status})`);
    }
    clearError();
    return response.json();
  } finally {
    clearTimeout(timeoutId);
  }
}

async function fetchGuess(word) {
  const params = new URLSearchParams({ word });
  if (state.gameId) params.set("game_id", state.gameId);
  const url = `${CONFIG.API_BASE}${CONFIG.GUESS_ENDPOINT}?${params.toString()}`;
  let lastError = null;

  for (let attempt = 1; attempt <= CONFIG.MAX_ATTEMPTS; attempt += 1) {
    if (attempt > 1) {
      showError(`Paleidžiamas serveris… (${attempt}/${CONFIG.MAX_ATTEMPTS})`);
    }

    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), CONFIG.REQUEST_TIMEOUT_MS);
      const response = await fetch(url, { signal: controller.signal });
      clearTimeout(timeoutId);

      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail || `Serverio klaida (${response.status})`);
      }

      clearError();
      return response.json();
    } catch (err) {
      lastError = err;
      const retryable =
        err.name === "AbortError" ||
        err.message.includes("Failed to fetch") ||
        err.message.includes("502") ||
        err.message.includes("503");

      if (retryable && attempt < CONFIG.MAX_ATTEMPTS) {
        await sleep(CONFIG.RETRY_DELAY_MS);
        continue;
      }
      break;
    }
  }

  if (lastError?.name === "AbortError") {
    throw new Error("Serveris neužsibudino laiku. Bandyk dar kartą po minutės.");
  }

  throw lastError || new Error("Nepavyko prisijungti prie serverio.");
}

async function fetchHint(bestRank) {
  const params = new URLSearchParams({
    game_id: state.gameId,
    best_rank: String(bestRank),
  });
  const url = `${CONFIG.API_BASE}${CONFIG.HINT_ENDPOINT}?${params.toString()}`;
  let lastError = null;

  for (let attempt = 1; attempt <= CONFIG.MAX_ATTEMPTS; attempt += 1) {
    if (attempt > 1) {
      showError(`Paleidžiamas serveris… (${attempt}/${CONFIG.MAX_ATTEMPTS})`);
    }
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), CONFIG.REQUEST_TIMEOUT_MS);
      const response = await fetch(url, { signal: controller.signal });
      clearTimeout(timeoutId);
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail || `Serverio klaida (${response.status})`);
      }
      clearError();
      return response.json();
    } catch (err) {
      lastError = err;
      const retryable =
        err.name === "AbortError" ||
        err.message.includes("Failed to fetch") ||
        err.message.includes("502") ||
        err.message.includes("503");
      if (retryable && attempt < CONFIG.MAX_ATTEMPTS) {
        await sleep(CONFIG.RETRY_DELAY_MS);
        continue;
      }
      break;
    }
  }

  if (lastError?.name === "AbortError") {
    throw new Error("Serveris neužsibudino laiku. Bandyk dar kartą po minutės.");
  }
  throw lastError || new Error("Nepavyko gauti užuominos.");
}

async function fetchSurrender() {
  const params = new URLSearchParams({ game_id: state.gameId });
  const url = `${CONFIG.API_BASE}${CONFIG.SURRENDER_ENDPOINT}?${params.toString()}`;
  let lastError = null;

  for (let attempt = 1; attempt <= CONFIG.MAX_ATTEMPTS; attempt += 1) {
    if (attempt > 1) {
      showError(`Paleidžiamas serveris… (${attempt}/${CONFIG.MAX_ATTEMPTS})`);
    }
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), CONFIG.REQUEST_TIMEOUT_MS);
      const response = await fetch(url, { signal: controller.signal });
      clearTimeout(timeoutId);
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail || `Serverio klaida (${response.status})`);
      }
      clearError();
      return response.json();
    } catch (err) {
      lastError = err;
      const retryable =
        err.name === "AbortError" ||
        err.message.includes("Failed to fetch") ||
        err.message.includes("502") ||
        err.message.includes("503");
      if (retryable && attempt < CONFIG.MAX_ATTEMPTS) {
        await sleep(CONFIG.RETRY_DELAY_MS);
        continue;
      }
      break;
    }
  }

  if (lastError?.name === "AbortError") {
    throw new Error("Serveris neužsibudino laiku. Bandyk dar kartą po minutės.");
  }
  throw lastError || new Error("Nepavyko pasiduoti.");
}

// --- Scoring Helpers ---
function rankToProgress(rank, total) {
  const n = Math.max(total || 0, 2);
  const r = Math.min(Math.max(rank, 1), n);
  return Math.round((1 - Math.log(r) / Math.log(n)) * 100);
}

function getScoreClass(similarity) {
  if (similarity >= CONFIG.WIN_THRESHOLD) return "score-exact";
  if (similarity >= 0.5) return "score-hot";
  if (similarity >= 0.3) return "score-warm";
  if (similarity >= 0.15) return "score-cool";
  return "score-cold";
}

function formatPositionLabel(position) {
  return `${position.toLocaleString("lt-LT")}`;
}

// --- Rendering ---
function createGuessRow(guess, isLatest) {
  const progress = rankToProgress(guess.position, state.totalWords);
  const scoreClass = getScoreClass(guess.similarity);
  const isExact = guess.similarity >= CONFIG.WIN_THRESHOLD;
  const row = document.createElement("div");
  row.className = `guess-row ${scoreClass}${isExact ? " exact-match" : ""}${isLatest ? " latest-guess" : ""}${guess.isHint ? " hint-row" : ""}`;
  row.dataset.lemma = guess.lemma;

  row.setAttribute("role", "listitem");
  row.innerHTML = `
    <div class="bar-track" role="progressbar" aria-valuenow="${progress}" aria-valuemin="0" aria-valuemax="100" aria-label="Progresas iki slapto žodžio">
      <div class="bar-fill" style="width: 0%"></div>
    </div>
    <span class="guess-word">${isExact ? '<svg class="win-check" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg>' : ""}${escapeHTML(guess.lemma)}</span>
    <div class="guess-position" aria-label="Pozicija žodyne">
      <span class="guess-position-num">${formatPositionLabel(guess.position)}</span>
    </div>
  `;

  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      const fill = row.querySelector(".bar-fill");
      if (fill) fill.style.width = `${progress}%`;
    });
  });

  return row;
}


function renderGuessList() {
  dom.guessList.innerHTML = "";

  if (state.guesses.length === 0) {
    dom.guessList.appendChild(createEmptyState());
    updateMeta();
    return;
  }

  const latest = state.guesses[state.guesses.length - 1];
  dom.guessList.appendChild(createGuessRow(latest, true));

  const rest = state.guesses.slice(0, -1).sort((a, b) => a.position - b.position);
  if (rest.length > 0) {
    const separator = document.createElement("hr");
    separator.className = "latest-separator";
    separator.setAttribute("aria-hidden", "true");
    dom.guessList.appendChild(separator);
    rest.forEach((guess) => {
      dom.guessList.appendChild(createGuessRow(guess, false));
    });
  }
  updateMeta();
}

function updateMeta() {
  if (!dom.meta) return;
  if (state.guesses.length === 0) {
    dom.meta.textContent = "";
    return;
  }
  const count = state.guesses.length;
  const mod10 = count % 10;
  const mod100 = count % 100;
  const word = mod10 === 1 && mod100 !== 11 ? "spėjimas" : mod10 >= 2 && mod10 <= 9 && (mod100 < 11 || mod100 > 19) ? "spėjimai" : "spėjimų";
  dom.meta.textContent = `${count} ${word}`;
}

function createEmptyState() {
  const div = document.createElement("div");
  div.id = "empty-state";
  div.className = "empty-state";
  div.innerHTML = `
    <div class="empty-icon" aria-hidden="true"><svg width="40" height="40" viewBox="0 0 40 40" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><circle cx="17" cy="17" r="9"/><line x1="24" y1="24" x2="32" y2="32"/><path d="M13.5 17h7"/></svg></div>
    <p class="empty-text">Pradėk žaidimą įvesdamas bet kokį lietuvišką žodį</p>
    <p class="empty-hint">Kuo žodis semantiškai artimesnis slaptam žodžiui, tuo aukštesnė jo pozicija</p>
  `;
  return div;
}

function updateStats() {
  updateHintButton();
  updateSurrenderButton();
  updateMeta();
}

function updateHintButton() {
  if (!dom.hintBtn) return;
  const bestPos =
    state.guesses.length > 0
      ? Math.min(...state.guesses.map((g) => g.position))
      : null;
  dom.hintBtn.disabled =
    state.isLoading || state.hasWon || state.hasSurrendered || bestPos === null || bestPos <= 1;
}

function updateSurrenderButton() {
  if (!dom.surrenderBtn) return;
  dom.surrenderBtn.disabled =
    state.isLoading || state.hasWon || state.hasSurrendered || state.guesses.length === 0;
}

async function handleSurrender() {
  if (state.isLoading || state.hasWon || state.hasSurrendered || state.guesses.length === 0) return;
  const confirmed = confirm("Pasiduoti ir atskleisti 10 artimiausių žodžių?");
  if (!confirmed) return;
  clearError();
  setLoading(true);
  try {
    const data = await fetchSurrender();
    const words = Array.isArray(data.words) ? data.words : [];
    const known = new Set(state.guesses.map((g) => g.lemma));
    for (const w of words) {
      if (!w || typeof w.lemma !== "string" || known.has(w.lemma)) continue;
      known.add(w.lemma);
      state.guesses.push({
        input: w.lemma,
        lemma: w.lemma,
        similarity: w.similarity,
        position: w.rank,
        isHint: true,
        isSurrender: true,
      });
    }
    state.hasSurrendered = true;
    const secret = words.length > 0 ? words[0] : null;
    showSurrender(secret ? secret.lemma : null);
    renderGuessList();
    updateStats();
    saveProgress();
  } catch (err) {
    if (isGameNotFound(err)) {
      console.warn("Stale game id on surrender, starting fresh:", state.gameId);
      clearProgress();
      state.gameId = null;
      await startNewGame();
      showError("Senas žaidimas nebegalioja — pradėtas naujas.");
      return;
    }
    console.error("Surrender error:", err);
    showError(err.message || "Nepavyko pasiduoti.");
  } finally {
    setLoading(false);
    dom.input.focus();
  }
}

async function handleHint() {
  if (state.isLoading || state.hasWon || state.hasSurrendered || state.guesses.length === 0) return;
  const bestPos = Math.min(...state.guesses.map((g) => g.position));
  if (bestPos <= 1) return;

  clearError();
  setLoading(true);
  try {
    const data = await fetchHint(bestPos);
    if (isDuplicate(data.lemma)) {
      highlightDuplicate(data.lemma);
      showError(`„${data.lemma}" jau atskleista! Spėk pats.`);
      return;
    }
    state.guesses.push({
      input: data.lemma,
      lemma: data.lemma,
      similarity: data.similarity,
      position: data.rank,
      isHint: true,
    });
    renderGuessList();
    updateStats();
    saveProgress();
    if (data.similarity >= CONFIG.WIN_THRESHOLD) {
      showWin();
      saveProgress();
    }
  } catch (err) {
    if (isGameNotFound(err)) {
      console.warn("Stale game id on hint, starting fresh:", state.gameId);
      clearProgress();
      state.gameId = null;
      await startNewGame();
      showError("Senas žaidimas nebegalioja — pradėtas naujas.");
      return;
    }
    console.error("Hint error:", err);
    showError(err.message || "Nepavyko gauti užuominos.");
  } finally {
    setLoading(false);
    dom.input.focus();
  }
}

function showWin() {
  state.hasWon = true;
  dom.winBanner.querySelector(".win-title").textContent = "Sveikiname!";
  dom.winBanner.querySelector(".win-text").innerHTML =
    `Atspėjai žodį per <span id="win-count">${state.guesses.length}</span> bandymų!`;
  dom.winCount = document.getElementById("win-count");
  dom.winBanner.hidden = false;
  dom.input.disabled = true;
  dom.submit.disabled = true;
}

function showSurrender(secret) {
  state.hasSurrendered = true;
  dom.winBanner.querySelector(".win-title").textContent = "Pasiduota";
  dom.winBanner.querySelector(".win-text").innerHTML = secret
    ? `Slaptas žodis: <strong>${escapeHTML(secret)}</strong> — rodomi 10 artimiausių.`
    : "Rodomi 10 artimiausių žodžių.";
  dom.winBanner.hidden = false;
  dom.input.disabled = true;
  dom.submit.disabled = true;
}

function hideWin() {
  state.hasWon = false;
  state.hasSurrendered = false;
  dom.winBanner.querySelector(".win-title").textContent = "Sveikiname!";
  dom.winBanner.hidden = true;
  dom.input.disabled = false;
  dom.submit.disabled = false;
}

async function startNewGame() {
  clearError();
  setLoading(true);
  try {
    const data = await fetchNewGame();
    clearProgress();
    state.gameId = data.game_id;
    state.guesses = [];
    state.hasWon = false;
    state.hasSurrendered = false;
    if (typeof data.total_words === "number") {
      state.totalWords = data.total_words;
    }
    hideWin();
    renderGuessList();
    updateStats();
    saveProgress();
    dom.input.value = "";
  } catch (err) {
    console.error("New game error:", err);
    showError(err.message || "Nepavyko sukurti naujo žaidimo.");
  } finally {
    setLoading(false);
    dom.input.focus();
  }
}

async function resetGame() {
  const confirmed = confirm(
    "Pradėti naują žaidimą su nauju slaptu žodžiu?"
  );
  if (!confirmed) return;
  await startNewGame();
}

// --- Error Display ---
function showError(message) {
  dom.error.textContent = message;
  dom.error.classList.add("visible");
  setTimeout(() => {
    dom.error.classList.remove("visible");
  }, 4000);
}

function clearError() {
  dom.error.classList.remove("visible");
}

// --- Loading State ---
function setLoading(loading) {
  state.isLoading = loading;
  dom.submit.disabled = loading || state.hasWon || state.hasSurrendered;
  dom.submit.classList.toggle("loading", loading);
  updateStats();
  if (loading) {
    dom.input.setAttribute("aria-busy", "true");
  } else {
    dom.input.removeAttribute("aria-busy");
  }
}

// --- Duplicate Check ---
function isDuplicate(lemma) {
  return state.guesses.some((g) => g.lemma === lemma);
}

function highlightDuplicate(lemma) {
  const rows = dom.guessList.querySelectorAll(".guess-row");
  rows.forEach((row) => {
    if (row.dataset.lemma === lemma) {
      row.classList.remove("shake");
      void row.offsetWidth;
      row.classList.add("shake");
    }
  });
}

// --- Form Submit ---
async function handleSubmit(event) {
  event.preventDefault();

  if (state.isLoading || state.hasWon || state.hasSurrendered) return;

  const word = dom.input.value.trim();
  if (!word) return;

  clearError();
  setLoading(true);

  try {
    const data = await fetchGuess(word);

    if (isDuplicate(data.lemma)) {
      highlightDuplicate(data.lemma);
      showError(`„${data.lemma}" jau buvo spėtas!`);
      dom.input.select();
      return;
    }

    state.guesses.push({
      input: data.input || word,
      lemma: data.lemma,
      similarity: data.similarity,
      position: data.rank,
    });

    renderGuessList();
    updateStats();
    saveProgress();

    if (data.similarity >= CONFIG.WIN_THRESHOLD) {
      showWin();
      saveProgress();
    }

    dom.input.value = "";
    dom.input.focus();
  } catch (err) {
    if (isGameNotFound(err)) {
      console.warn("Stale game id, starting a fresh game:", state.gameId);
      clearProgress();
      state.gameId = null;
      await startNewGame();
      showError("Senas žaidimas nebegalioja — pradėtas naujas. Spėk dar kartą!");
      return;
    }
    if (isWordNotFound(err)) {
      console.warn("Unknown word:", word);
      showError(`Žodžio „${word}" nėra žodyne. Bandyk kitą.`);
      dom.input.select();
      return;
    }
    console.error("Guess error:", err);
    showError(err.message || "Nepavyko prisijungti prie serverio.");
  } finally {
    setLoading(false);
  }
}

// --- Escape HTML ---
function escapeHTML(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

// --- Init ---
async function init() {
  const health = await fetchHealth();
  if (health && typeof health.total_words === "number") {
    state.totalWords = health.total_words;
  }

  let restored = loadProgress();
  if (restored && isLegacyGameId(state.gameId)) {
    console.warn("Dropping legacy game id from before deterministic ids:", state.gameId);
    clearProgress();
    state.gameId = null;
    state.guesses = [];
    state.hasWon = false;
    state.hasSurrendered = false;
    restored = false;
  }
  if (restored) {
    renderGuessList();
    updateStats();
    if (state.hasWon) {
      showWin();
    } else if (state.hasSurrendered) {
      const secret = state.guesses.length > 0
        ? [...state.guesses].sort((a, b) => a.position - b.position)[0].lemma
        : null;
      showSurrender(secret);
      state.hasSurrendered = true;
    }
  } else {
    await startNewGame();
  }

  dom.form.addEventListener("submit", handleSubmit);
  dom.resetBtn.addEventListener("click", resetGame);
  if (dom.hintBtn) dom.hintBtn.addEventListener("click", handleHint);
  if (dom.surrenderBtn) dom.surrenderBtn.addEventListener("click", handleSurrender);
  dom.input.focus();
}

init();
