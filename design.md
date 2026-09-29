# BioNexus — Field Notes design language

BioNexus is a research workspace presented like a contemporary scientific field notebook: paper, ink, measured annotation, and traceable evidence. This system replaces the earlier dark instrument language. Its public page has a more editorial rhythm; dense analysis views use the same colors and materials with tighter spacing.

## Source and intent

The flat, ruled enterprise clarity in the curated IBM DESIGN.md analysis and the editorial workflow hierarchy in the Airtable analysis informed this direction. These are references from awesome-design-md/getdesign.md, not official BioNexus specifications or copied brand assets. BioNexus uses its own forest green, warm paper palette, typography, and research content.

## Foundation

| Role | Value | Use |
|---|---|---|
| Paper | `#F5F3EC` | App canvas |
| Sheet | `#FFFEFA` | Content panels, tables, controls |
| Soft sheet | `#F9F8F3` | Reading surfaces |
| Sidebar | `#F0F1E9` | Navigation |
| Ink | `#1D2F2A` | Primary text |
| Secondary ink | `#40524A` | Descriptions |
| Annotation | `#57655C` | Labels and metadata |
| Rule | `#CBD3C5` | Dividers and panel borders |
| Forest | `#16634E` | Primary actions, links, selection |
| Forest hover | `#0F4D3C` | Action hover |
| Blue | `#30557E` | Neutral information and scientific channels |
| Ochre | `#8F531A` | Caution and moderate confidence |
| Red | `#A1362E` | Actual errors only |

Tokens live in `bioai-platform/frontend/src/app/globals.css`; Tailwind maps them through `bioai-platform/frontend/tailwind.config.ts`. Existing token aliases such as `accent-cyan` and `glass-border` are compatibility names. They resolve to the new palette, regardless of their historical names.

## Typography and spacing

- Georgia is the editorial display face for headings. Arial/Helvetica is the compact interface face for controls and body copy. Monospace is reserved for accessions, values, labels, and provenance.
- Landing display: 48–86px, regular weight, tight tracking, short lines. Product titles remain smaller and legible at high density.
- Body: 14–18px with generous line height. Use 12px uppercase mono labels sparingly to mark sections and data types.
- Use 4px spacing increments, 5–8px corners, and one-pixel rules. Panels are opaque and flat. Do not use blur, glow, elevated shadows, ornamental gradients, or moving decorative elements.

## Components and behavior

- Primary action: filled forest green, white text, at least 42px high. Secondary action: bordered sheet with ink text. Focus: visible 2px forest outline with offset.
- Navigation: a solid forest active state, no colored stripe. The sidebar has a distinct sage surface; the top bar is a sheet.
- Content cards and data surfaces: opaque white sheet, rule border, 8px radius or less, no elevation. Tables retain tabular numerals and explicit empty/loading/error states.
- Scientific colors convey distinct information and confidence. Color is paired with labels, never used as the only indicator. Missing, measured zero, pending, unavailable, and failed remain separate states.
- Motion is limited to purposeful state changes and short hover transitions. Respect reduced motion. The landing page has no auto-playing decoration.
- At narrow widths, method rows and editorial columns stack; actions retain touch targets and keyboard focus.

## Content principles

Describe the method and its limits concretely. Do not fabricate example measurements, hits, affinities, confidence values, or run records to make the interface feel populated. Explain exploratory NGS preview separately from production planning and external execution. A grounded AI explanation is not independent biological validation.

## Verification

Review semantic headings, labels, focus order, contrast, responsive overflow, reduced motion, and status language using the Web Design Guidelines. Inspect the landing and representative workflows with Playwright CLI when a browser binary is available; use build and static checks as a fallback, reporting that limitation plainly.
