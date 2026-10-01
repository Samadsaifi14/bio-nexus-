# BioNexus free-tier infrastructure map

This document uses the **free-for-dev** catalog as a discovery source for hosted
developer services. The catalog itself is not a runtime dependency and should
not be vendored into BioNexus.

The operating rule is simple: prefer an existing BioNexus service when it
already solves the problem, add at most one provider per capability, and never
make a scientific result depend on a third-party free tier unless the
dependency and fallback are explicit.

## Current baseline

| Capability | BioNexus today | Decision |
| --- | --- | --- |
| Frontend hosting | Vercel | Keep. Next.js production deploys and previews are already integrated. |
| Scientific/backend compute | Hugging Face Space + external/deployment execution paths | Keep compute separate from the frontend. Do not move scientific workloads into a convenience free tier merely to reduce cost. |
| Authentication/data/storage | Supabase | Keep. Avoid duplicating database or object storage without a concrete requirement. |
| Error/performance telemetry | Sentry hooks in frontend and backend | Keep and finish configuring through environment variables. Do not add a second error tracker. |
| CI/security | GitHub Actions, CodeQL, Semgrep, dependency audits, Dependabot | Keep. Frontend lint, typecheck and production build are required gates. |
| Application cache/queue | Redis-compatible URL, optional | Keep optional. The application must continue to degrade explicitly when cache infrastructure is unavailable. |

## Free-for-dev candidates that fit BioNexus

### Uptime monitoring

Use **one** hosted uptime provider such as Better Stack or UptimeRobot, not
both.

Recommended checks:

- Web: `https://bio-nexus-ebon.vercel.app/`
- API liveness: `https://samad14-bio-nexus-api.hf.space/health`
- Frequency: five minutes is sufficient for the current project.
- Alert only on repeated failures to avoid false alarms during a deployment.

GitHub deployment CI now performs immediate post-deploy checks as the first
line of defense. External uptime monitoring is the independent second line.

### Synthetic workflow checks

**Checkly** is useful only when BioNexus needs browser/API transaction checks
that go beyond simple uptime. High-value candidates are:

1. landing page -> Analyze navigation;
2. a deterministic public/read-only API probe;
3. a non-destructive structure-viewer page load;
4. a fixture-backed scientific-result rendering check.

Never point a scheduled synthetic check at a costly docking, MD, BLAST or NGS
execution endpoint unless the test uses an explicitly bounded fixture and its
resource budget is documented.

### Metrics and logs

**Grafana Cloud** is a reasonable future destination when backend metrics,
logs, and traces need one cross-service view. Do not add it while Sentry and
platform logs already answer the operational question. Add it when BioNexus has
a concrete dashboard/alert requirement such as request latency by scientific
module, worker queue depth, or cache hit rate.

### Coverage reporting

**Codecov** can be added after coverage is collected consistently in CI.
Coverage percentage must remain a software-quality signal only; it is not a
claim of scientific validation.

Suggested scope:

- backend unit/contract tests;
- frontend utility/component tests when a stable test suite exists;
- scientific benchmark pass/fail remains separate from code coverage.

### Edge security and custom domain

**Cloudflare** becomes useful if BioNexus adopts a custom domain and needs DNS,
WAF, rate limiting, or an additional edge security layer. Do not place it in
front of the current Vercel hostname solely because a free tier exists.

## Rules for credentials and free tiers

- Store credentials in Vercel, Hugging Face, Supabase, or GitHub encrypted
  environment/secrets facilities; never commit them.
- No frontend-exposed secret keys. Only variables intentionally safe for the
  browser may use a `NEXT_PUBLIC_` prefix.
- Treat free-tier limits as operational constraints, not reliability
  guarantees.
- A provider outage must not silently change a scientific method or substitute
  a different scientific engine.
- Observability failure must never alter scientific data.
- Review provider limits before enabling a new integration because free plans
  can change.

## Optimization decisions implemented with this pass

1. PDBe Mol* is loaded only on structure/docking screens instead of before
   interactivity on every route.
2. Baseline browser security headers are emitted by Next.js.
3. Canonical/Open Graph/Twitter metadata, robots rules, and a public sitemap
   are provided natively by Next.js.
4. Frontend CI has an explicit TypeScript gate and the project exposes Next.js'
   built-in bundle analyzer.
5. Deployment CI verifies both the public frontend and backend health after a
   release.
6. Existing Sentry, Supabase, Vercel, Hugging Face, GitHub security tooling and
   Redis hooks are reused rather than duplicated.

## Next activation order

When credentials/accounts are available, activate external services in this
order:

1. one uptime provider for the web and `/health`;
2. one bounded synthetic check for a deterministic BioNexus workflow;
3. Codecov after stable coverage collection exists;
4. Grafana Cloud only when operational metrics justify another telemetry
   backend;
5. Cloudflare only with a custom-domain/edge-security requirement.

This order keeps the operational stack understandable and prevents free-tier
vendor sprawl from becoming a reliability problem of its own.
