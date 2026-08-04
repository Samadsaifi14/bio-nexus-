# Bio Nexus — Design System

Canonical source of truth for the whole-site redesign (supersedes the older
BioFlow AI draft this file used to hold). Implemented in
`bioai-platform/frontend/src/app/globals.css` and
`bioai-platform/frontend/tailwind.config.ts` — when these files and this doc
disagree, the files win and this doc is wrong.

## 1. Identity

A **bioluminescent lab instrument that feels alive**. Not a SaaS dashboard, not
a 2003 bioinformatics portal. Dark-only, cinematic, scientific.

- Canvas: near-black indigo HUD surfaces. Pure black kills depth; translucent
  panels layer over a deep indigo void.
- The instrument metaphor runs through the chrome: scan-lines, pulsing job
  status dots, monospace data panels, glow only where a signal is live.
- Motion is one authored moment per view (see §7), never a generic entrance on
  every section.

## 2. Color System

### 2.1 Canvas & surfaces

| Token | Value | Role |
|---|---|---|
| `--bg-void` | `#04040A` | app background, page base |
| `--bg-surface-0` | `#080812` | cards, panels, data cards |
| `--bg-surface-1` | `#0D0D1A` | inputs, hover, second level |
| `--bg-surface-2` | `#111122` | raised panels, table rows |
| `--bg-surface-3` | `#151528` | modals, dropdowns, popovers |
| `--glass-border` | `rgba(100,110,180,0.12)` | hairline borders everywhere |
| `--data-card-bg` | `rgba(8,8,18,0.96)` | near-opaque scientific output |
| `--hud-bg` | `rgba(13,13,26,0.90)` | 3D viewer chrome |

### 2.2 Accents — bioluminescent triad

| Token | Value | Contrast on `surface-0` | Use |
|---|---|---|---|
| `--accent-cyan` | `#2DD4BF` | 10.7:1 | primary accent, active nav, CTAs |
| `--accent-purple` | `#8B93D6` | 6.9:1 | secondary/alternate accent (e.g. MSA, docking) |
| `--accent-amber` | `#E0A94E` | 9.5:1 | warnings that are *not* errors (e.g. RMSD) |

All three pass WCAG AA on every surface tier. Do not add a fourth accent.

### 2.3 Text tiers (AA-verified)

| Token | Value | Contrast on `surface-0` | Role |
|---|---|---|---|
| `--text-primary` | `#F0F0FF` | 17.7:1 | headings, primary content |
| `--text-secondary` | `#A5AEC6` | 9.1:1 | secondary copy, descriptions |
| `--text-muted` | `#848CA4` | 5.9:1 | labels, metadata, disabled |

`text-muted` was raised from `#4A4F6A` (2.5:1 — failed AA on 441 usages). The
hierarchy is preserved: three clearly separated tiers, all legible.

### 2.4 Semantic — scientific confidence bands

Confidence is a **statistical statement, never a pass/fail**. Red is reserved
for real errors only (job failed, API down). `#EF4444` is the only error color.

| Band | Value | Meaning shown to user |
|---|---|---|
| Very high | `#2DD4BF` (teal) | "Very high statistical confidence" |
| High | `#60A5FA` (blue) | "High statistical confidence" |
| Moderate | `#FBBF24` (amber) | "Moderate — worth a closer look" |
| Low | `#94A3B8` (gray) | "Low confidence — not necessarily wrong, just uncertain" |

Bands are never color-only: always pair with the text label (colorblind-safe).
Tailwind tokens: `confidence-very-high`, `confidence-high`, `confidence-moderate`,
`confidence-low`.

## 3. Typography

| Role | Font | Source |
|---|---|---|
| Display (hero, headings) | **Geist Sans** | `geist/font/sans` (self-hosted) |
| UI (body, labels, buttons) | **Geist Sans** | same |
| Data (sequences, accessions, raw output) | **Geist Mono** | `geist/font/mono` |

- Fonts are self-hosted via the `geist` package and applied through
  `--font-geist-sans` / `--font-geist-mono` CSS variables in `layout.tsx`.
  No runtime Google Fonts fetch. No `next/font/google` imports.
- Tailwind classes: `font-sans`, `font-display`, `font-body` → Geist Sans;
  `font-mono` → Geist Mono.
- Headings: weight 600, `letter-spacing: -0.02em`.
- Body measure 65–75ch. Display max 6rem. Tracking floor −0.04em.
- Type scale: `12 / 14 / 16 / 20 / 28 / 40 / 56px`, body line-height 1.5.

## 4. Spacing, Radius, Depth

- Base unit 4px. Scale `4 / 8 / 12 / 16 / 24 / 32 / 48 / 64 / 96`.
- Max content width 1280px (`max-w-content`).
- Radius: 16px cards (`rounded-2xl`), 12–14px panels, 10px buttons/inputs,
  8px badges/pills. Pills are for small controls only.
- Elevation is declared **once**: border XOR shadow, never a 1px border under a
  wide soft shadow (the "ghost card" is banned). Shadows carry an offset and a
  soft blur; a zero-offset halo is decoration.

## 5. Component System

CSS component classes in `globals.css` (`@layer components`):

| Class | Role | Notes |
|---|---|---|
| `.data-card` | scientific output (near-opaque) | charts, tables, sequences, scores |
| `.glass-card` | general card | translucent, 16px radius |
| `.glass-panel` | inset panel | `blur(32px) saturate(180%)` |
| `.liquid-glass` | hero/nav chrome only | the "wow" surface; never over data |
| `.clay` / `.clay-*` | tactile low-stakes controls | toggles, sliders, mode pickers only |
| `.hud` / `.hud-legend` | 3D viewer chrome | near-opaque, sits in the viewer |
| `.btn-critical` | primary CTA | solid teal gradient, dark text |
| `.btn-primary` | secondary solid | `--accent-cyan` fill |
| `.btn-ghost` | quiet action | border + text |
| `.btn-critical-danger` | destructive | red, only for real destructive actions |
| `.input-flat` / `.input-glass` | data-entry inputs | flat is precision-first |
| `.nav-item` (+ `.active`) | sidebar items | active = cyan fill `--accent-cyan-10` |
| `.badge-cyan` / `.badge-purple` | status badges | uppercase mono, pill |

Banned: nested cards, gradient text, kicker/eyebrow labels above headings,
section numbers (01/02/03), emoji as icons, monospace as costume (only for
code/data/measurement), glass/blur as decoration, sparklines/progress rings as
content, hard offset shadows outside a neobrutalist world, sketch/doodle SVG
scenes.

## 6. Icons

- **Phosphor** (`@phosphor-icons/react`), weight regular/semi-bold, sizes
  16/20/24. One consistent stroke weight across the whole app.
- `lucide-react` is fully removed (migration is its own commit).
- No emoji or unicode glyphs as icons anywhere.

## 7. Motion Principles

- Page transitions: 200ms ease-out, fade + 8px slide (framer-motion).
- Job status: slow pulsing `--accent-cyan` dot during active steps — the
  instrument is working, not the page broken. Not a generic spinner.
- Hero: animated sequence "typewriter" or helix canvas linework.
- One authored moment per view. Respect `prefers-reduced-motion` (already
  global in `globals.css`).
- Durations 150–300ms. Exponentially eased, from an already-visible default.

## 8. Legacy cleanup

- The `!important` Tailwind override layer at the end of `globals.css`
  (`.bg-white`, `.text-gray-*`, `.border-teal-*`, ...) is a transitional crutch
  for legacy light-mode pages. **Delete it in its own commit** after the
  legacy pages (`(auth)`, `shared/[token]`, AIInterpretation) are converted to
  native dark tokens.
- Theme toggle/context machinery is removed — Bio Nexus is dark-only.

## 9. Verification

- `npx tsc --noEmit` — clean (unused imports are errors).
- `npm run build` and `npm run lint` must pass before push.
- Contrast table in §2 is the source of truth for token values; any new tint
  must be AA-verified on all five surfaces.
