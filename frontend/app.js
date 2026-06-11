// ============================================================
// KONTEKSTO — Game Engine (Frontend)
// ============================================================

const CONFIG = {
  API_BASE: "https://daliusber-konteksto.hf.space",
  GUESS_ENDPOINT: "/api/v1/guess",
  WIN_THRESHOLD: 0.9999,
  REQUEST_TIMEOUT_MS: 120_000,
  MAX_ATTEMPTS: 6,
  RETRY_DELAY_MS: 8_000,
};

// --- State ---
const state = {
  guesses: [],
  isLoading: false,
  hasWon: false,
};

// --- DOM References ---
const dom = {
  form: document.getElementById("guess-form"),
  input: document.getElementById("guess-input"),
  submit: document.getElementById("guess-submit"),
  error: document.getElementById("input-error"),
  guessList: document.getElementById("guess-list"),
  emptyState: document.getElementById("empty-state"),
  guessCount: document.getElementById("guess-count"),
  bestScore: document.getElementById("best-score"),
  winBanner: document.getElementById("win-banner"),
  winCount: document.getElementById("win-count"),
};

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// --- API ---
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
  // Map raw cosine similarity (-1 to 1) to a 0-100 display percentage
  // Using a clamped linear mapping from 0..1 range
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
    <span class="guess-rank">#${guess.rank}</span>
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

  // Animate bar fill after paint
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      const fill = row.querySelector(".bar-fill");
      if (fill) fill.style.width = `${percent}%`;
    });
  });

  return row;
}

function renderGuessList() {
  // Sort by similarity descending
  const sorted = [...state.guesses].sort((a, b) => b.similarity - a.similarity);

  // Assign ranks
  sorted.forEach((g, i) => { g.rank = i + 1; });

  // Clear and rebuild
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
  } else {
    dom.bestScore.textContent = "—";
  }
}

function showWin() {
  state.hasWon = true;
  dom.winCount.textContent = state.guesses.length;
  dom.winBanner.hidden = false;
  dom.input.disabled = true;
  dom.submit.disabled = true;
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
  dom.submit.disabled = loading;
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
      // Force reflow to restart animation
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

    // Check for duplicate lemma
    if (isDuplicate(data.lemma)) {
      highlightDuplicate(data.lemma);
      showError(`„${data.lemma}" jau buvo spėtas!`);
      dom.input.select();
      return;
    }

    // Add guess
    state.guesses.push({
      input: data.input || word,
      lemma: data.lemma,
      similarity: data.similarity,
      rank: 0,
    });

    renderGuessList();
    updateStats();

    // Check for win
    if (data.similarity >= CONFIG.WIN_THRESHOLD) {
      showWin();
    }

    // Clear input
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
function init() {
  dom.form.addEventListener("submit", handleSubmit);
  dom.input.focus();
}

init();
