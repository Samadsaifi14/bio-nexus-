# CODE SAMPLE TEMPLATE — how to share code with your AI

> Paste one small, *representative* snippet of your code into this file and
> share it. That gives the AI a reference for **your** conventions so every
> later instruction ("apply the design system", "fix the chart", "add a page")
> is implemented in your style, not a generic one.

## When to use

- You're about to ask for a big refactor / new feature and want the result to
  match your existing code.
- Something the AI built "almost" looks right but doesn't match how you write
  components.
- You're starting a fresh session and want to re-establish your conventions.

## What to include

1. **One component** (a card, a panel, a viewer wrapper) — full file.
2. **One page / route** — the layout skeleton only, if you have one.
3. **Your conventions** (tick what applies).

---

## 1 · A representative component

```tsx
'use client';

// Paste ONE component you consider "typical" of how you build UI.
// Include imports, props pattern, styling approach, and how you handle state.
```

## 2 · A representative page / route

```tsx
// Optional — paste the skeleton of one page (imports + layout structure).
```

## 3 · Conventions checklist (tick what applies)

- [ ] `'use client'` at top of interactive components
- [ ] Tailwind utility classes inline (no CSS module files)
- [ ] Custom CSS classes live in `src/app/globals.css` under `@layer components`
- [ ] Colors from the design tokens: `text-text-primary`, `text-text-secondary`, `text-text-muted`, `accent-cyan`, `glass-card`, `data-card`
- [ ] Icons from `lucide-react` with `className="w-4 h-4"`
- [ ] Animations from `@/lib/animations` (`fadeUp`, `stagger`, `cardHover`, `fadeIn`)
- [ ] Data fetching with `fetch("/api/backend/...")` (no axios)
- [ ] Forms: controlled inputs, `useState`, no form library
- [ ] Default export for components; named export for shared UI primitives
- [ ] font stacks: `font-display` (Space Grotesk), body default (Inter), `font-mono` (JetBrains Mono)
- [ ] Style by trust zone: data → flat/opaque (`data-card`), chrome/status → `glass`, discrete controls → clay, 3D viewers → HUD

## 4 · Notes / anything unusual about your codebase

<!-- Anything the AI should know: naming conventions, folder rules,
     server components vs client, legacy Tailwind classes you override, etc. -->

---

### Example (filled in)

```tsx
'use client';

import { motion } from 'framer-motion';
import { fadeUp } from '@/lib/animations';
import type { BlastHitSummary } from '@/types/pipeline';

export function ScoreBars({ hits }: { hits: BlastHitSummary[] | null }) {
  return (
    <motion.div variants={fadeUp} className="data-card p-6">
      <h2 className="text-lg font-semibold text-text-primary mb-4">Score Distribution</h2>
      ...
    </motion.div>
  );
}
```

> Copy this whole file, delete the instructions you don't need, fill the
> blocks, and send it back to the AI in your next message.
