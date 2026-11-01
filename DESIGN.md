---
name: Konteksto
description: A calm midnight word-guessing game for Lithuanian learners.
colors:
  signal-violet: "hsl(250 88% 72%)"
  deep-ink: "#0a0a0f"
  ink-panel: "#12121a"
  pale-word: "#eceaf2"
  muted-pencil: "#a5a3b8"
  faint-pencil: "#7e7c94"
  verdict-green: "#22c55e"
  caution-amber: "#f59e0b"
  error-red: "#ef4444"
  bar-cold: "hsl(240 65% 68%)"
  bar-cool: "hsl(200 75% 58%)"
  bar-warm: "hsl(35 95% 62%)"
  bar-hot: "hsl(140 65% 55%)"
typography:
  display:
    fontFamily: "Sora, -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif"
    fontSize: "2rem"
    fontWeight: 800
    lineHeight: 1.2
    letterSpacing: "-0.03em"
  title:
    fontFamily: "Sora, -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif"
    fontSize: "1.25rem"
    fontWeight: 700
    lineHeight: 1.3
  body:
    fontFamily: "Sora, -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif"
    fontSize: "0.9375rem"
    fontWeight: 400
    lineHeight: 1.6
  label:
    fontFamily: "Sora, -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif"
    fontSize: "0.6875rem"
    fontWeight: 500
    lineHeight: 1.4
    letterSpacing: "0.08em"
rounded:
  sm: "0.5rem"
  md: "0.75rem"
  lg: "1rem"
  xl: "1.25rem"
  full: "9999px"
spacing:
  xs: "0.25rem"
  sm: "0.5rem"
  md: "1rem"
  lg: "1.5rem"
  xl: "2rem"
  2xl: "3rem"
components:
  button-submit:
    backgroundColor: "{colors.signal-violet}"
    textColor: "{colors.pale-word}"
    rounded: "{rounded.lg}"
    padding: "0"
    size: "52px"
    height: "52px"
    width: "52px"
  button-ghost:
    backgroundColor: "rgba(255, 255, 255, 0.03)"
    textColor: "{colors.muted-pencil}"
    rounded: "{rounded.lg}"
    padding: "0.5rem 1rem"
  input-guess:
    backgroundColor: "rgba(255, 255, 255, 0.06)"
    textColor: "{colors.pale-word}"
    rounded: "{rounded.lg}"
    padding: "0.25rem 0.25rem 0.25rem 1rem"
  guess-row:
    backgroundColor: "rgba(255, 255, 255, 0.03) + full-height temperature fill"
    textColor: "{colors.pale-word}"
    rounded: "{rounded.lg}"
    padding: "0.5rem 1rem"
  stat-card:
    backgroundColor: "rgba(255, 255, 255, 0.03)"
    textColor: "{colors.pale-word}"
    rounded: "{rounded.lg}"
    padding: "0.5rem 1rem"

# Design System: Konteksto

## Overview

**Creative North Star: "The Midnight Study Desk"**

Konteksto is a dark, quiet room where a learner sits alone with Lithuanian words late at night. The interface stays out of the way: a single near-black ink surface with a faint violet vignette at the top, pencil-grey text, generous breathing room. Color is never decoration — it only ever means progress. A violet focus ring marks whatever matters right now (the focused input, the latest guess tinted violet), and the similarity bars run cold-to-hot like an instrument measuring how close a guess lands to the hidden word.

The aesthetic philosophy is calm, focused, and encouraging. Feedback arrives fast but gently — soft transitions, a brief celebratory banner on a win, never casino energy. Nothing here should feel like a classroom test or a playful cartoon owl; it is a study desk with one good lamp.

**Key Characteristics:**
- Dark-first: near-black backgrounds, light text, translucent glass cards.
- Color means progress: violet accent + cold→hot score ramp, muted everywhere else.
- Soft glass, confident accent: rounded translucent surfaces; full color only on the submit button and meaningful states.
- Fast and gentle motion: expo easing, short transitions, celebration only on wins.

## Colors

A midnight palette: deep ink grounds, pencil-grey text, one violet voice, and a verdict + score ramp reserved for feedback.

### Primary
- **Signal Violet** (hsl(250 88% 72%)): The single accent. Submit button, input focus ring and caret, latest-guess highlight, hint words, links. Its rarity is the point.

### Neutral
- **Deep Ink** (#0a0a0f): Page background.
- **Ink Panel** (#12121a): Secondary background layer.
- **Pale Word** (#eceaf2): Primary text.
- **Muted Pencil** (#a5a3b8): Secondary text (subtitle, hints, reset buttons, placeholders).
- **Faint Pencil** (#7e7c94): Muted text (labels, footer).
- **Glass Card** (rgba(255, 255, 255, 0.03)): Default card/input surface; hover lifts to 0.06, input focus to 0.09.
- **Subtle Border** (rgba(255, 255, 255, 0.06)): Default hairline for cards and inputs.

### Tertiary
- **Verdict Green** (#22c55e): Win state only — win banner, exact-match rows, hottest score class.
- **Caution Amber** (#f59e0b): Warning states.
- **Error Red** (#ef4444): Input errors.
- **Score Cold** (hsl(240 65% 68%)), **Score Cool** (hsl(200 75% 58%)), **Score Warm** (hsl(35 95% 62%)), **Score Hot** (hsl(140 65% 55%)): Similarity bar ramp from distant to near-miss.

### Named Rules
**The Violet-Means-Progress Rule.** Accent color and focus ring appear only as feedback — focus, latest guess, score bars, win state. Chrome, labels, and idle surfaces stay pencil-grey on glass.

## Typography

**Display Font:** Sora (with -apple-system, system-ui fallback)
**Body Font:** Sora (with -apple-system, system-ui fallback)
**Label Font:** Sora throughout; rank numerals use tabular figures. No monospace costume.

**Character:** Sora throughout, tight-tracked and heavy at the logo, small and widely-tracked for uppercase labels. No serif, no display face — the words being guessed are the typography.

### Hierarchy
- **Display** (800, 2rem/1.5rem mobile, -0.03em): Logo wordmark only, solid pale text.
- **Title** (700, 1.25rem): Win banner heading.
- **Body** (400–600, 0.875–1rem, 1.6): Guess words at 600, input at 500, hints at 400.
- **Label** (500, 0.6875rem, uppercase, 0.08em): Stat labels, rank denominators.

## Layout

Single centered column, max-width 560px, full-viewport flex column. Sections stack: header (logo + subtitle + guess-count meta) → detached input + submit → guess list → bottom action bar (hint / new game) → footer. Rhythm follows the spacing scale (0.25–3rem); cards breathe with 0.5–1rem internal padding. Below 480px the shell tightens and the action bar sticks to the viewport bottom. One breakpoint, one column — density never changes, only air.

## Elevation & Depth

Flat-by-default with ring-as-feedback. Resting surfaces carry no shadow — depth comes from tonal layering (glass cards on ink, 6% borders). A focus ring appears only as a response to state.

- **Accent focus ring** (`0 0 0 2px hsl(250 88% 72% / 0.35)`): Input focus companion.
- **Latest outline** (1px pale + 1px ring): Latest guess only — borrowed prominence without a second accent hue.
- **Card rest** (`0 2px 12px rgba(0, 0, 0, 0.25)`): Barely-there grounding for cards.
- **Bar color** (full-height translucent temperature fill): Similarity is the row background; text stays legible via shadow + ellipsis.

**The Flat-By-Default Rule.** Surfaces are flat at rest. A focus ring appears only as a response to state (focus, win). The latest guess gets a neutral pale outline + dashed separator — not the violet ring, so violet still means progress. Bars never glow.

## Shapes

Soft glass geometry: 0.5rem small controls, 0.75rem buttons/cards/rows, 1rem input and banner, 1.25rem reserved, full-round pills for bars and tracks. Borders are 1px hairlines (subtle white or violet-tinted accent). The backdrop is one flat ink surface with a faint top vignette — no blobs, no decoration behind content.

## Components

### Buttons
- **Shape:** 1rem radius input, 1rem detached submit, 1rem action-bar buttons.
- **Primary:** 52px-min detached Signal Violet submit with white arrow icon and `var(--space-sm)` gap from the input; hover brightens 1.15× and scales 1.04; active scales 0.96; loading swaps icon for spinner.
- **Action Bar:** Two large thumb-reach buttons (hint with accent border when usable, new game) in a 2-column grid; sticky bottom on mobile.

### Cards / Containers
- **Corner Style:** 1rem radius rows, banner, inputs.
- **Background:** Glass card (3% white); guess rows carry a full-height translucent temperature fill whose width encodes rank progress.
- **Shadow Strategy:** Flat at rest; latest guess gains a neutral pale outline + dashed separator below; exact match gains green tint + border.
- **Border:** 1px subtle; pale on latest, green-tinted on exact.
- **Internal Padding:** 0.5rem 1rem; guess rows flex word-left / rank-right, min-height 52px.

### Inputs / Fields
- **Style:** Translucent 6% fill, hairline border, 1rem radius, 1rem/500 input text, muted placeholder; submit lives outside the field as its own target.
- **Focus:** Fill deepens to 9%, border turns accent-tinted, accent glow appears.
- **Error / Disabled:** Error text small red below, expanding via max-height; submit dims to 50% when disabled.

### Navigation
Single screen; no nav component. Header is identity + live guess count (`N spėjimai`, tabular numerals). Actions live in the bottom bar (hint, new game with icons). Footer is a single muted credit line.

### Guess Row (Signature Component)
Word (700 weight, ellipsis-truncated, violet when hinted) left, large tabular rank numeral right; full-height temperature fill behind (width = log-scaled rank progress, 55% mix so text stays legible). Latest row is outlined pale with a dashed separator beneath it; the list below stays rank-sorted. New rows land without entrance choreography; duplicates shake.

## Do's and Don'ts

### Do:
- **Do** keep the page near-black and let violet + score colors carry all meaning.
- **Do** use the focus ring only for focus, latest guess, and wins — never glow, never decoration.
- **Do** keep Sora everywhere; numerals tabular where ranks align.
- **Do** respect `prefers-reduced-motion` — all animation collapses to near-zero.

### Don't:
- **Don't** add a light theme, a second accent hue, or serif/italic display type.
- **Don't** put color on idle chrome — labels, footers stay pencil-grey; placeholders use secondary text for contrast.
- **Don't** add accounts, nav bars, or multi-screen flows; this is one screen by design.
- **Don't** invent testimonials, scores, or press; the empty state is honest, not marketing.
