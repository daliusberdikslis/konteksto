// ============================================================
// KONTEKSTO — Game Engine (Frontend)
// ============================================================

const CONFIG = {
  API_BASE: "https://daliusber-konteksto.hf.space",
  GUESS_ENDPOINT: "/api/v1/guess",
  HEALTH_ENDPOINT: "/health",
  WIN_THRESHOLD: 0.9999,
  REQUEST_TIMEOUT_MS: 120_000,
  MAX_ATTEMPTS: 6,
  RETRY_DELAY_MS: 8_000,
  STORAGE_VERSION: 1,
  DEFAULT_TARGET: "krepšinis",
};

// --- State ---
const state = {
  guesses: [],
  isLoading: false,
  hasWon: false,
  targetLemma: CONFIG.DEFAULT_TARGET,
  totalWords: null,
};

// --- DOM References ---
const dom = {
  form: document.getElementById("guess-form"),
  input: document.getElementById("guess-input"),
  submit: document.getElementById("guess-submit"),
  error: document.getElementById("input-error"),
  guessList: document.getElementById("guess-list"),
  guessCount: document.getElementById("guess-count"),
  bestScore: document.getElementById("best-score"),
  bestPosition: document.getElementById("best-position"),
  winBanner: document.getElementById("win-banner"),
  winCount: document.getElementById("win-count"),
  resetBtn: document.getElementById("reset-game"),
};

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function storageKey() {
  return `konteksto:v${CONFIG.STORAGE_VERSION}:${state.targetLemma}`;
}

// --- Progress persistence ---
function saveProgress() {
  try {
    const payload = {
      version: CONFIG.STORAGE_VERSION,
      target: state.targetLemma,
      totalWords: state.totalWords,
      guesses: state.guesses,
      hasWon: state.hasWon,
      savedAt: new Date().toISOString(),
    };
    localStorage.setItem(storageKey(), JSON.stringify(payload));
  } catch (err) {
    console.warn("Could not save progress:", err);
  }
}

function loadProgress() {
  try {
    const raw = localStorage.getItem(storageKey());
    if (!raw) return false;

    const data = JSON.parse(raw);
    if (
      data.version !== CONFIG.STORAGE_VERSION ||
      data.target !== state.targetLemma ||
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
  } catch (err) {
    console.warn("Could not clear progress:", err);
  }
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

async function fetchGuess(word) {
  const url = `${CONFIG.API_BASE}${CONFIG.GUESS_ENDPOINT}?word=${encodeURIComponent(word)}`;
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

// --- Scoring Helpers ---
function similarityToPercent(similarity) {
  const clamped = Math.max(0, Math.min(1, similarity));
  return Math.round(clamped * 100);
}

function getScoreClass(similarity) {
  if (similarity >= CONFIG.WIN_THRESHOLD) return "score-exact";
  if (similarity >= 0.5) return "score-hot";
  if (similarity >= 0.3) return "score-warm";
  if (similarity >= 0.15) return "score-cool";
  return "score-cold";
}

function formatPositionLabel(position) {
  if (state.totalWords) {
    return `#${position} <span class="position-of">iš ${state.totalWords.toLocaleString("lt-LT")}</span>`;
  }
  return `#${position}`;
}

// --- Rendering ---
function createGuessRow(guess) {
  const percent = similarityToPercent(guess.similarity);
  const scoreClass = getScoreClass(guess.similarity);
  const isExact = guess.similarity >= CONFIG.WIN_THRESHOLD;

  const row = document.createElement("div");
  row.className = `guess-row ${scoreClass}${isExact ? " exact-match" : ""}`;
  row.setAttribute("role", "listitem");
  row.dataset.lemma = guess.lemma;

  row.innerHTML = `
    <div class="guess-position" aria-label="Pozicija žodyne">
      <span class="guess-position-num">${formatPositionLabel(guess.position)}</span>
    </div>
    <div class="guess-word-col">
      <span class="guess-word">${escapeHTML(guess.input)}</span>
      ${guess.lemma !== guess.input.toLowerCase() ? `<span class="guess-lemma">→ ${escapeHTML(guess.lemma)}</span>` : ""}
    </div>
    <div class="guess-bar-col ${scoreClass}">
      <div class="bar-track">
        <div class="bar-fill" style="width: 0%"></div>
      </div>
      <span class="guess-score">${percent}%</span>
    </div>
  `;

  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      const fill = row.querySelector(".bar-fill");
      if (fill) fill.style.width = `${percent}%`;
    });
  });

  return row;
}

function renderGuessList() {
  const sorted = [...state.guesses].sort((a, b) => b.similarity - a.similarity);

  dom.guessList.innerHTML = "";

  if (sorted.length === 0) {
    dom.guessList.appendChild(createEmptyState());
    return;
  }

  sorted.forEach((guess) => {
    dom.guessList.appendChild(createGuessRow(guess));
  });
}

function createEmptyState() {
  const div = document.createElement("div");
  div.id = "empty-state";
  div.className = "empty-state";
  div.innerHTML = `
    <div class="empty-icon">💭</div>
    <p class="empty-text">Pradėk žaidimą įvesdamas bet kokį lietuvišką žodį</p>
    <p class="empty-hint">Kuo arčiau semantiškai tavo žodis yra slapto žodžio, tuo aukštesnis balas</p>
  `;
  return div;
}

function updateStats() {
  dom.guessCount.textContent = state.guesses.length;

  if (state.guesses.length > 0) {
    const best = Math.max(...state.guesses.map((g) => g.similarity));
    dom.bestScore.textContent = `${similarityToPercent(best)}%`;

    const bestPos = Math.min(...state.guesses.map((g) => g.position));
    dom.bestPosition.textContent = `#${bestPos}`;
  } else {
    dom.bestScore.textContent = "—";
    dom.bestPosition.textContent = "—";
  }
}

function showWin() {
  state.hasWon = true;
  dom.winCount.textContent = state.guesses.length;
  dom.winBanner.hidden = false;
  dom.input.disabled = true;
  dom.submit.disabled = true;
}

function hideWin() {
  state.hasWon = false;
  dom.winBanner.hidden = true;
  dom.input.disabled = false;
  dom.submit.disabled = false;
}

function resetGame() {
  const confirmed = confirm(
    "Ištrinti visus spėjimus ir pradėti iš naujo?"
  );
  if (!confirmed) return;

  clearProgress();
  state.guesses = [];
  state.hasWon = false;
  hideWin();
  renderGuessList();
  updateStats();
  clearError();
  dom.input.value = "";
  dom.input.focus();
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
  dom.submit.disabled = loading || state.hasWon;
  dom.submit.classList.toggle("loading", loading);
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

  if (state.isLoading || state.hasWon) return;

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
  if (health) {
    if (health.target_lemma) {
      state.targetLemma = health.target_lemma;
    }
    if (typeof health.total_words === "number") {
      state.totalWords = health.total_words;
    }
  }

  const restored = loadProgress();
  if (restored) {
    renderGuessList();
    updateStats();
    if (state.hasWon) {
      showWin();
    }
  }

  dom.form.addEventListener("submit", handleSubmit);
  dom.resetBtn.addEventListener("click", resetGame);
  dom.input.focus();
}

init();
