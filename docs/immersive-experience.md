# BioNexus Perspective

The homepage tells a three-part research story with original illustrative geometry:
Input (double helix), Analysis (folded molecular form), and Evidence (abstract assembly).
These are conceptual illustrations, not molecular predictions or scientific measurements.

## Implementation

- `frontend/src/components/experience/ImmersiveStory.tsx`: accessible content, CSS sticky scene, GSAP text reveals and ScrollTrigger-driven scene progress.
- `ResearchCanvas.tsx`: lazy Three.js rendering; demand-driven frames, visibility checks, resize handling and GPU resource cleanup.
- `SplineCanvas.tsx`: optional official Spline runtime adapter for a published `.splinecode` scene.
- `WebGLCursor.tsx`: a short-lived pointer ring on desktop, with the native pointer retained and no input interception.
- `WorkspaceExperience.tsx`: a shared introduction across workspace routes. Scientific tables and plots are not animation targets.
- `frontend/src/app/immersive.css`: responsive design and accessibility fallbacks.

Paths above are relative to `bioai-platform/`. The molecular factory is
`frontend/src/lib/experience/scene.ts`. Its shapes are original, not third-party assets.

## Working default

Without `NEXT_PUBLIC_SPLINE_SCENE_URL`, the site uses the original Three.js scene.
Desktop scrolling changes the scene from the helix through the folded form to the
evidence assembly. The content uses normal document scrolling and CSS sticky positioning.
Mobile, reduced-motion and unavailable-WebGL experiences use the static poster.
Pause motion replaces the scene with the poster and stops the story's GSAP animations.

## Native Spline publication: remaining handoff

The cloud Spline editor reported unsupported WebGL during implementation, so a native
Spline project and production `.splinecode` URL have **not** been published or verified.
The exported GLB and runtime integration are ready for this step:

1. Import `bioai-platform/frontend/public/scenes/bionexus-research.glb` into Spline.
2. Preserve the three group names: `Input`, `Analysis`, `Evidence`.
3. The import arranges groups side by side for inspection. Set each group's X position
   to zero for the published composition; the runtime also resets X to zero.
4. Frame the helix with a perspective camera at Z around 10.8, a 36-degree field of
   view and a transparent background. Confirm its framing in Spline because imported
   camera/material settings can differ. Add soft environment illumination if needed.
5. Keep group scale at 1. Export as Code and publish the scene. Copy the actual
   `.splinecode` URL; do not use an editor URL or public iframe URL.
6. Set `NEXT_PUBLIC_SPLINE_SCENE_URL` on the existing BioNexus Vercel frontend project
   and redeploy. This value is public and must not contain secrets.
7. Verify all three chapters, resizing, reduced motion and pause/resume against that
   native scene. Failed loads or missing named groups retain the static poster.

The native Spline path is an integration pending end-to-end verification. Do not describe
the default Three.js renderer as a published Spline scene.

## Regenerate the import asset

With Node.js 24 and the frontend dependencies installed:

```bash
cd bioai-platform/frontend
node scripts/export-research-scene.mjs
```

## Local verification without external build telemetry

```bash
cd bioai-platform/frontend
npm ci
npm run typecheck
BIONEXUS_LOCAL_VERIFY=1 NEXT_TELEMETRY_DISABLED=1 SENTRY_DSN='' NEXT_PUBLIC_SENTRY_DSN='' SENTRY_AUTH_TOKEN='' npm run build
```

`BIONEXUS_LOCAL_VERIFY=1` bypasses the Sentry build wrapper locally. Normal deployment
configuration is unchanged. No analysis backend, statistical method, scientific values,
authentication logic or route URLs were changed by this visual implementation.

## Verification performed

- Production compilation and static generation: pass (42 static pages), using the
  local verification configuration above.
- TypeScript and ESLint on modified components: pass.
- Chromium desktop: real WebGL scene loaded; scrolling changed the rendered scene;
  pause unmounted the canvas and resume restored it; method selection opened the
  corresponding method link.
- 390-pixel mobile: no horizontal overflow; no research WebGL canvas mounted.
- Reduced motion: no research WebGL canvas mounted.
- BLAST, docking and NGS/RNA-seq routes rendered the shared workspace introduction.
- No uncaught browser page errors in these checks. Local backend requests were
  unavailable; these checks do not validate scientific computations or services.
- Native Spline publication and its end-to-end rendering remain unverified.
