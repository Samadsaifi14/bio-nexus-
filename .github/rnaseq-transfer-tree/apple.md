# Bio Nexus — Apple Light Theme Redesign

Master planning + execution document. Read this before touching any code.

**Status:** Phase 1 (token remap + theme toggle) complete → Phase 2 not started
**Owner:** Samad
**Repo:** `C:\Users\hp\Desktop\bio-nexus`
**Supersedes:** the earlier "Refine & Elevate / dark-only" decision. This adds light mode as a user-switchable theme alongside dark, not a replacement — the toggle that decision deleted is coming back.

---

## 0. Vision

Bio Nexus should feel like a calm, precise scientific instrument, not a dashboard. The reference isn't "light mode as dark-mode-inverted" — it's apple.com product pages (typography, whitespace, restraint) crossed with macOS System Settings / Control Center (frosted materials, grouped hierarchy, physical depth via shadow not gradient).

### Non-negotiable constraints (shapes every token below)

The design must stay legible on a **low-nit, low-resolution display in direct sunlight**. That rules out:

- Pure white-on-white or near-invisible hairlines (`rgba(0,0,0,0.03)` disappears outdoors — floor is `0.06`)
- Thin/light font weights for body text at small sizes
- Frosted glass as the *only* separator between stacked surfaces — glass needs a hairline or shadow backing it up, because blur/saturation effects wash out under high ambient light
- Color-only state indication (teal-on-white contrast must clear AA on its own, never rely on saturation alone)

Every token spec below carries its own contrast ratio. If a future edit breaks one, that's a bug.

---

## 1. Token Spec (`globals.css` / `tailwind.config.ts` remap)

### 1.0 Theme architecture (toggle, not replacement)

Since both themes must coexist, tokens can't be flatly reassigned — they need to be scoped per theme and switched at runtime:

1. Add `data-theme="light" | "dark"` on `<html>` (or `<body>`), toggled via a small script that runs **before paint** (inline in `<head>` or a `next-themes`-style approach) to avoid a flash-of-wrong-theme on load.
2. Every semantic token in `globals.css` becomes two declarations:

```css
:root, [data-theme="dark"] {
  --bg-void: #0A0A0F;         /* existing dark values, unchanged */
  --text-primary: #F5F5F7;
  /* ...existing dark tokens... */
}
[data-theme="light"] {
  --bg-void: #F5F5F7;         /* new light values from §1.1–1.9 below */
  --text-primary: #1D1D1F;
  /* ...new light tokens... */
}
```

3. Persist the user's choice (`localStorage` key, e.g. `bio-nexus-theme`) and respect `prefers-color-scheme` as the default for first-time visitors only — never override an explicit user choice.
4. Toggle control lives in the app shell header (icon button, sun/moon) and ideally also in account/settings — put it back where "Refine & Elevate" removed it.

> **Scope note:** this makes Phase 1 double in size vs. a flat remap — you're adding a full second token set *and* the switching mechanism. Budget accordingly. It's still the right phase to do first, just bigger.

- Components/pages using tokens (the majority of the ~100 files) need **zero changes** — they just render differently based on which `data-theme` is active, same as before.
- The ~20 hardcoded-dark files (§2.2) and the four Three.js scenes (§2.3) are the ones that need real conditional logic (`theme === 'light' ? ... : ...`) rather than pure CSS, since they're not driven by CSS variables.

**Tailwind bridge:** Tailwind config colors must point at CSS variables (e.g. `void: 'var(--bg-void)'`, `surface: { 0: 'var(--bg-surface-0)', ... }`, `'text-primary': 'var(--text-primary)'`) so `bg-void`, `bg-surface-*`, `text-text-*`, `border-glass-border` classes resolve per active theme. Same for `boxShadow` and `backgroundImage` entries — token-ize anything hardcoded to dark rgba.

### 1.1 Canvas & surfaces (stepped gray system)

| Token | Old (dark) | New (light) | Notes |
|---|---|---|---|
| `--bg-void` | near-black | `#F5F5F7` | Apple system gray, canvas |
| `--bg-surface-0` | darkest panel | `#FFFFFF` | Cards, modals |
| `--bg-surface-1` | panel | `#F5F5F7` | Recessed sections |
| `--bg-surface-2` | raised panel | `#EBEBF0` | Nested/secondary panels |
| `--bg-surface-3` | highest panel | `#E3E3E8` | Pressed/active states |

### 1.2 Text

| Token | New value | Contrast on `#F5F5F7` |
|---|---|---|
| `--text-primary` | `#1D1D1F` | 16.1:1 (AAA) |
| `--text-secondary` | `#6E6E73` | 5.4:1 (AA for normal text) |
| `--text-muted` | `#86868B` | 3.9:1 — AA large-text/UI only, not body copy. Bump to `#6E6E73` anywhere it's used for readable sentences, not just labels/captions |

### 1.3 Borders / hairlines

| Token | New value |
|---|---|
| `--border-glass-border` | `rgba(0,0,0,0.10)` on white surfaces, `rgba(0,0,0,0.08)` on `#F5F5F7` |
| `--border-hairline` | `rgba(0,0,0,0.06)` — floor value, never go lower (sunlight legibility) |

### 1.4 Glass / material

```css
.liquid-glass {
  background: rgba(255,255,255,0.65);
  backdrop-filter: blur(20px) saturate(180%);
  -webkit-backdrop-filter: blur(20px) saturate(180%);
  border: 1px solid rgba(0,0,0,0.08);
  box-shadow: 0 1px 2px rgba(0,0,0,0.04), 0 8px 24px rgba(0,0,0,0.06);
}
```

**Rule:** every glass surface gets a hairline border, not just blur — blur alone is invisible in bright ambient light.

### 1.5 Brand teal — re-tuned for white backgrounds

| Token | Old use | New value | Contrast |
|---|---|---|---|
| `--teal-cta` | primary action | `#0E9384` | 4.52:1 white text on teal (AA) |
| `--teal-tint` | glow/accent | `#2DD4BF` | unchanged — decorative only, never load-bearing for text/contrast |
| `--confidence-very-high` | pLDDT/score bands | `#0E9384` | re-tuned; verify against new white chart backgrounds |
| `--confidence-moderate` | warn band | `#D97706` (amber) | was probably fine on dark; re-check on white |
| `--confidence-low` | low band | `#DC2626` (red) | re-check on white |

### 1.6 Clay / neumorphism → light

Old clay depended on dark ambient shadow. Light neumorphism needs a **dual light-source shadow**, not a darkened single shadow, or it reads as "dirty" rather than "soft":

```css
.clay {
  background: #F5F5F7;
  box-shadow:
    6px 6px 12px rgba(0,0,0,0.06),
    -6px -6px 12px rgba(255,255,255,0.9);
}
```

### 1.7 Data-card (charts, trees, scores — near-opaque, zero blur)

```css
.data-card {
  background: #FFFFFF;
  border: 1px solid rgba(0,0,0,0.08);
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}
```

Keep this component zero-blur as before — it's the one surface where legibility of dense scientific data trumps material aesthetic.

### 1.8 HUD (3D viewer chrome)

Was dark-on-transparent over a dark 3D scene. On light: `rgba(255,255,255,0.85)` panel, `blur(12px)`, `#1D1D1F` text — must stay legible over whatever the AlphaFold/Docking canvas background becomes (see §2.3).

### 1.9 Spacing / radius / type

- **Radius:** cards 12px → 18px, buttons 8px → 12px, pills unchanged (full)
- **Spacing scale:** widen section padding ~20–25% (Apple pages breathe more than dense dark dashboards)
- **Type:** current code uses **Geist Sans** (display + body) / **Geist Mono** (code/data). The earlier direction proposed Space Grotesk (display) / Geist (body) / JetBrains Mono (code/data) — confirm before switching fonts, since a font swap touches every page. Either way, adjust letter-spacing `-0.01em` to `-0.02em` on large display sizes to match Apple's optical tightening, and bump body line-height to 1.5–1.6 for light-background readability.

---

## 2. Component Inventory

### 2.1 Auto-flips (semantic-token-only — verify, don't rewrite)

Everything built on `bg-void`, `bg-surface-0/1/2/3`, `text-text-primary/secondary/muted`, `border-glass-border` flips automatically once §1 lands. This is the majority of ~100 files. Action: spot-check ~10 representative pages after Phase 1, don't hand-edit.

### 2.2 Hardcoded-dark fix list (~20 files, explicit)

| File | Issue | Fix |
|---|---|---|
| `(dashboard)/layout.tsx` | sidebar/header hardcoded rgba dark values | replace with tokens |
| `AuditInsightPanel.tsx` | hardcoded dark bg | token |
| `TutorialWalkthrough.tsx` | hardcoded dark bg | token |
| `CursorGlow.tsx` | glow tuned for dark canvas | re-tune glow color/opacity for light canvas (invert from "light glow on dark" to "soft teal glow, much lower opacity, on light") |
| `AlphaFoldViewer.tsx` | `bg-black/40` overlay | `bg-white/70` or token equivalent |
| `DomainArchitecture.tsx` | tooltip hardcoded dark | token |
| `shared/[token]/page.tsx` | audit for hardcoded values | token |
| Three.js canvases: `DNAHelix`, `Structure`, `Docking`, `MSA` | scene background + material colors tuned for dark void | new light-mode scene variants — see §2.3 |

### 2.3 Three.js light-mode scenes (the hard part)

These aren't CSS-token-fixable — they're WebGL scene/material colors, and since dark must keep working too, each component needs to read the active theme (context/hook, not CSS var) and branch its scene/material setup. Each needs a light variant alongside the existing dark one:

- **DNAHelix (landing hero):** dark void → light scene means the helix itself must carry more contrast than the background gives for free. Recommend: light gray/white gradient background (`#F5F5F7` → `#FFFFFF`), helix strands in teal (`#0E9384`)/deep navy for contrast, subtle drop shadow under the geometry (fake AO) since you lose the "glow in the dark" depth cue entirely.
- **Structure / Docking / MSA viewers:** same principle — pLDDT coloring already carries its own palette (blue→orange), so the scene background is what needs to flip (`#FFFFFF` or very light gray), not the molecule coloring itself. Verify pLDDT color scale still reads clearly on white (it likely does, since it's designed for either).

---

## 3. Per-Surface Specs

### 3.1 Landing page

- **New nav:** frosted toolbar (`.liquid-glass`), sticky, condenses on scroll (Apple's nav-shrink pattern)
- **Hero:** giant type, line-by-line scroll reveal (stagger ~60ms/line, spring easing), DNA helix as light-mode 3D centerpiece per §2.3
- **Database marquee:** restyle from dark ticker to light logo strip — `#FFFFFF` cards with hairline
- **Feature sections:** alternating text-left/visual-right asymmetric layout, generous vertical rhythm (apple.com uses ~120–160px section gaps on desktop)
- **CTA + footer:** apple.com-style — centered, minimal, generous whitespace, footer link grid on `#F5F5F7`

### 3.2 Auth

Frosted card centered on canvas, no dark void — a soft radial teal-tinted gradient behind the card (very low opacity, ~4–6%) for warmth without noise.

### 3.3 App shell / sidebar

Frosted translucent sidebar (`.liquid-glass` variant, `#FFFFFF` at 0.8 opacity rather than 0.65 — sidebars need more opacity than hero glass to stay legible against scrolling content behind them). Grouped nav: **Tools / Activity / System** headers in text-muted caps; active item gets a filled pill in teal-tint at low opacity + teal-cta text/icon.

### 3.4 Dashboard

Reordered: greeting → prominent **"New Analysis"** CTA (single most prominent element, teal-cta) → usage/stats row (data-card style) → quick-tools grid (icon + label cards, clay-light) → recent activity list.

### 3.5 Tool page template (build once, apply to ~35 pages)

Build out fully on **Analyze** first: input panel (flat input style, unchanged pattern) → pipeline progress (existing Supabase-driven step UI, restyle chrome only) → results (data-card grid). This becomes the template; don't touch the other 34 until this one is signed off.

### 3.6 Data viewers (AlphaFold/Docking/MSA/PhyloTree)

HUD toolbar restyle per §1.8, legend restyle to light `hud-legend`, scene backgrounds per §2.3.

---

## 4. Animation Spec

- **Spring system:** single shared spring config, damping ≈ 1.0 (critically damped, no bounce — matches Apple's restrained motion, not playful overshoot), interruptible (framer-motion `useSpring` / `AnimatePresence` with layout transitions)
- **Scroll reveals:** `useScroll` + `useTransform` on landing hero + feature sections, opacity/y-offset stagger, no more than ~8–10 elements animating simultaneously (perf on low-end devices, which matters given the low-nit/low-res hardware constraint)
- **Page transitions:** blur+scale material entrance between routes (`filter: blur(4px)→blur(0)`, `scale: 0.98→1`, ~200–250ms)
- **Micro-interactions:** button press scale (0.97), card hover lift (2–4px translateY + shadow increase), toggle/segmented control spring per existing Clay components
- **3D tilt/parallax:** subtle (±4–6deg max) on dashboard quick-tool cards and landing feature visuals — disable entirely on touch devices
- **`prefers-reduced-motion`:** hard rule — every spring/scroll-reveal/parallax/tilt above must have a static fallback (opacity fade only, no transform) gated on this media query. Test explicitly in Phase 7, don't assume it inherited from the dark-mode implementation.

---

## 5. Icon Treatment

- Phosphor icons, switch active set to **duotone weight** (fill + outline in two tones) for a more "crafted" feel than flat regular weight
- Sidebar icons get **rounded container chips** (8px radius, `bg-surface-2` idle → teal-tint/10 active)
- Icon color: `text-secondary` idle → teal-cta active/hover
- Audit for icons currently hardcoded to a dark-mode color value (likely a handful in HUD/legend components) — these need explicit fixing, they won't auto-flip

---

## 6. Execution Order

1. **Phase 1 — Token remap + theme toggle** (`globals.css`, `tailwind.config.ts`, pre-paint theme script + toggle control). Build, spot-check ~10 pages. This is the biggest leverage/lowest-risk step — do it first and verify before anything else.
2. **Phase 2 — Hardcoded-dark cleanup** (§2.2), including Three.js scene light variants (§2.3 — hardest, budget the most time here).
3. **Phase 3 — Landing page rebuild.**
4. **Phase 4 — App shell** (sidebar/header/nav grouping/transitions).
5. **Phase 5 — Dashboard + Analyze template page.**
6. **Phase 6 — Motion system + icon migration**, applied across what's already rebuilt.
7. **Phase 7 — Verification** (below). Then propagate the Analyze template to the remaining ~35 tool pages as a follow-on pass (separate ticket).

---

## 7. Verification Checklist

- [ ] `tsc --noEmit` — zero errors
- [ ] `npm run lint` — zero errors
- [ ] `npm run build` — succeeds
- [ ] AA contrast table filled in for every text/bg pair in §1.2 (spot-check with a contrast checker, not assumption)
- [ ] `prefers-reduced-motion: reduce` verified in browser devtools emulation — confirms static fallbacks fire, in both themes
- [ ] Manual check on a display with brightness dialed down + simulated glare (or just outdoors) — the actual constraint driving this whole plan
- [ ] Grep for remaining hardcoded dark hex/rgba values outside the §2.2 list (something will be missed on first pass)
- [ ] Three.js scenes checked at both default and low-brightness, in both themes
- [ ] Toggle regression pass: every page/component walked in both themes, not just light — verify existing dark mode wasn't broken by the token restructuring in §1.0
- [ ] No flash-of-wrong-theme on hard page reload (verify the pre-paint theme script actually runs before first render)
- [ ] Theme choice persists across reload and across routes
