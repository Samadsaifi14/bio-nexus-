# design.md — BioFlow AI Design System

## 1. Direction
Synthesis of your two references:
- **Supari Studios** → cinematic darkness, oversized type, atmosphere, motion as a feature.
- **Acova AI** → precision, structure, scientific credibility, restrained color.

Target feel: **a scientific instrument that feels alive** — not a SaaS dashboard, not a 2003-era bioinformatics portal.

## 2. Color System

### 2.1 Canvas (dark only for prototype)
```css
--bg-base:      #0A0E14;  /* near-black navy — pure black kills depth */
--bg-surface:   #11161F;  /* cards, panels */
--bg-elevated:  #1A212E;  /* modals, dropdowns, popovers */
--border-subtle:#232B3A;
```

### 2.2 Accent — "Bioluminescent Teal"
```css
--accent:        #2DD4BF;
--accent-bright: #5EEAD4;  /* hover */
--accent-glow:   rgba(45, 212, 191, 0.15); /* soft glow / highlight bg */
```

### 2.3 Text
```css
--text-primary:   #E6EDF3;
--text-secondary: #8B97A8;
--text-tertiary:  #5C6878;
```

### 2.4 Semantic — Scientific Confidence Bands
This is the direct fix for the "100% accurate" problem from the PRD. **Never use red/green here** — these aren't pass/fail.

| Band | E-value range | Color | Meaning shown to user |
|---|---|---|---|
| Very High | < 1e-50 | `#2DD4BF` (accent) | "Very high statistical confidence" |
| High | 1e-50 – 1e-10 | `#60A5FA` | "High statistical confidence" |
| Moderate | 1e-10 – 1e-3 | `#FBBF24` | "Moderate — worth a closer look" |
| Low | > 1e-3 | `#94A3B8` | "Low confidence — not necessarily wrong, just uncertain" |

True red (`#F87171`) is reserved **only** for actual errors (job failed, API down) — never for a scientific result. A student should never read "low confidence" as "you did something wrong."

## 3. Typography
| Role | Font | Weights |
|---|---|---|
| Display (hero, headers) | Space Grotesk | 500, 700 |
| UI (body, labels, buttons) | Inter | 400, 500, 600 |
| Sequences, accessions, raw data | JetBrains Mono | 400, 500 |

Type scale: `12 / 14 / 16 / 20 / 28 / 40 / 56px`, line-height 1.5 for body, 1.1 for display.

## 4. Spacing & Layout
- Base unit: 4px. Scale: `4 / 8 / 12 / 16 / 24 / 32 / 48 / 64 / 96`.
- Max content width: 1280px. Sequence/data panels can go full-bleed within their container.
- Border radius: 8px (cards), 6px (buttons/inputs), 4px (badges) — avoid pill shapes except status badges.

## 5. Core Components

**Sequence Display Block** — monospace, `--bg-elevated` background, horizontal scroll on overflow, line numbers in `--text-tertiary`, copy-to-clipboard button. Matched-region highlight = `--accent-glow` background + `--accent` underline.

**Confidence Badge** — pill, colored per §2.4, format: `E-value: 2e-67 · Very High Confidence`.

**Job Status Indicator** — a slow pulsing dot in `--accent` during active steps, not a generic spinner. Reinforces "instrument working," not "page broken."

**"What does this mean?" Expandable** — small `(?)` icon inline next to a term → popover (`--bg-elevated`) with a 1–2 sentence plain-English explanation, optional link to `/learn`.

**Wizard Step Indicator** — horizontal, numbered, current step in `--accent`, completed steps with checkmark, 200ms transition between steps.

**Buttons**
- Primary: `--accent` fill, `--bg-base` text, `--accent-bright` on hover.
- Secondary: transparent, `--border-subtle` border, `--text-primary` text.
- Ghost: text-only, `--accent` on hover.

## 6. Motion Principles
- Page transitions: 200ms ease-out, fade + 8px slide.
- No blank-loading screens — always a skeleton or contextual status string.
- Hero: animated sequence "typewriter" effect (CSS or canvas, cheap to run).

## 7. Iconography
- Lucide icons (already in your stack), 1.5px stroke, sizes 16/20/24.

## 8. Documentation Site Design (`/learn`)

- **Layout**: Centered content (max-width 880px), topic pages with back navigation, sticky right-side section nav for long pages
- **Topic cards**: Same glass-card pattern as /analyze — icon + title + description in a 2-column grid
- **Code examples**: `font-mono` on `bg-elevated` background, with horizontal scroll for long lines
- **Glossary**: A–Z listing with letter dividers, term in `font-mono` semibold, definition in `text-text-secondary`
- **LearnPopover**: Small `(?)` icon in `text-accent-cyan/60` next to term → click opens floating glass-card popover (max-width 320px) with 1-2 sentence explanation + optional "Learn more →" link in accent cyan

## 9. Accessibility
- All `--accent` on `--bg-base` text combinations pass WCAG AA at ≥14px.
- Confidence bands are never color-only — always paired with the text label (colorblind-safe, and this is scientific data where ambiguity matters).
- Tutorial walkthrough has keyboard navigation (Tab/Enter + Escape to close)
- Sequence data rendered in monospace (`font-mono`) — never sans-serif
