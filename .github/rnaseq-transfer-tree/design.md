# BioNexus — Research in motion

BioNexus is a scientific workspace for moving from a biological question to inspectable evidence. Its visual language is calm, tactile and precise. The landing page invites exploration; the app shell, method catalog and dashboard help researchers resume work, choose a method and read its status.

## Direction

The curated awesome-design-md examples informed the use of editorial hierarchy and modular information, adapted to BioNexus. The system borrows no logos, exact layouts or brand palette. The Taste Skill guides the public page, while the Web Design Guidelines guide labels, focus, keyboard access, contrast and responsive behavior.

## Palette

Muted sea-glass greens keep large surfaces quiet. Deeper values carry text and controls. These choices are design judgments, not claims that a hue is biologically or medically optimal. Contrast follows WCAG 2.2 guidance.

| Role | Value | Use |
|---|---|---|
| Canvas | `#F7F8F5` | Workspace background |
| Sheet | `#FFFFFD` | Reading and data surfaces |
| Wash | `#F1F6F2` | Secondary surfaces |
| Sidebar | `#EAF2ED` | Persistent navigation |
| Ink | `#203C38` | Headings and primary data |
| Secondary ink | `#4C6761` | Explanatory copy |
| Annotation | `#526B64` | Labels and metadata |
| Rule | `#D6E1D9` | Layout separation |
| Sea glass | `#2C6F65` | Actions and active navigation |
| Information | `#426F84` | Neutral scientific information |
| Caution | `#865C35` | Warning and moderate confidence |
| Error | `#A54D45` | Actual failure only |

Text colors meet 4.5:1 on the canvas and sheet; the action color exceeds 4.5:1 with white text. Scientific channels retain their distinct semantic hues. Labels and shapes accompany color so confidence, status and evidence class never depend on hue alone.

## Voice and typography

Use a humanist sans stack (`Trebuchet MS`, `Segoe UI`, Arial) for reading and controls, Palatino/Georgia for short editorial headlines, and monospace for accessions, values and provenance. This is the interpretation of the request for “phonetics for writing”: natural, speakable phrasing and a readable cadence rather than dense jargon or invented scientific claims. Questions lead method discovery; specific inputs, outputs and limits follow.

Examples: “What does this sequencing run actually support?” and “Similarity alone does not establish function.” Keep measured zero, missing data, pending work, failure and an unavailable service distinct.

## Layout and behavior

- The landing opens with a research-record illustration that contains no sample result data. A method explorer lets people choose NGS, BLAST, docking or MD and updates the input, inspectable output and interpretation boundary. Direct links open each workflow.
- The workspace shell provides a recognizable page title, persistent navigation and a clear new-analysis action. The mobile drawer closes on Escape, backdrop activation or navigation.
- The catalog supports field filters and text search with a real empty state. The dashboard prioritizes starting points and real recent jobs; usage and counts come from the backend.
- Responsive columns stack without hiding the route to a method. Cards are selected by content and behavior, not a uniform three-column template.

## Motion

Entrance motion establishes hierarchy. Method switching and filtered results crossfade over 200–300ms; navigation and hover respond in 120–420ms. Page transitions use a short fade and vertical offset. Motion does not imply scientific progress or create fake live status. No persistent decorative loop is required. `prefers-reduced-motion` removes spatial movement and keeps states legible.

## Scientific integrity

Do not invent hits, affinities, variant counts, job records or confidence. Exploratory NGS preview, production planning and external execution are separate. The hosted MD workflow is implicit-solvent OpenMM. AI grounding checks compare explanations to recorded evidence; they do not independently validate biology. The frontend renders backend-emitted values and states with provenance where available.

## Implementation and review

Design tokens: `bioai-platform/frontend/src/app/globals.css`; experience layout and interaction: `src/app/experience.css`; Tailwind aliases: `tailwind.config.ts`. Legacy token names remain for existing workflows while mapping to the new palette. Review keyboard access, focus, semantic labels, responsive overflow, status language, contrast and reduced motion. Playwright CLI is the browser check when Chrome is available.
