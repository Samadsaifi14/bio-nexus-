# Security Policy

## Reporting a vulnerability

Email the maintainer directly rather than opening a public issue. Include
steps to reproduce or a proof of concept where possible. You will get a
response within a week.

## Implemented controls

This section maps what the codebase actually does to the OWASP ASVS 4.x
sections those controls belong to. It is a plain-language summary, not a
formal certification.

| Control | Where | ASVS reference |
| --- | --- | --- |
| Supabase JWTs are signature-verified: HS256 locally when `SUPABASE_JWT_SECRET` is set, otherwise checked against `GET /auth/v1/user`. Expired, forged, and malformed tokens are rejected. Verification fails closed on network errors. | `backend/app/services/auth.py` | V2 (Authentication), V3 (Session) |
| Every protected endpoint resolves the caller through `require_user_id`; row ownership is enforced per user via Supabase RLS on `profiles.id` / FK columns. | routers under `backend/app/routers/` | V4 (Access Control) |
| API keys (`sk_bio_…`) are scoped, hashed at rest, and accepted via `X-API-Key` as an alternative to browser sessions. | `app/services/auth.py`, `app/routers/api_keys.py` | V3.5 |
| All user-supplied URLs (`pdb_url`) pass an allowlist validator before fetch; only known hosts such as RCSB and ESM Atlas are reachable. Internal/link-local addresses are blocked. | `app/services/ssrf.py`, callers in `docking.py`, `function_predict.py` | V12 (Files & Resources), V14.4 |
| SMILES strings are percent-encoded before being sent to PubChem CACTUS; responses are validated as real SDF payloads before shell-out conversion. | `app/tools/docking.py::smiles_to_pdbqt` | V5 (Validation) |
| Containers run as a non-root uid-1000 user; the HF Space image installs fpocket/Vina from pinned versions. | `Dockerfile`, `backend/Dockerfile` | V14 (Configuration) |
| Daily job quotas are enforced per user at the application layer for pipelines, docking, and sequencing; guests share a pooled quota until they sign in. | `app/services/rate_limit.py`, wired into pipeline/sequencing/AI routers | V4 (Access Control) |
| Dependency vulnerabilities are audited in CI: pip-audit for Python, npm audit (production deps) for the frontend. Dependabot opens weekly update PRs for pip, npm, and GitHub Actions. | `.github/workflows/security.yml`, `.github/dependabot.yml` | V14.2 |
| Semgrep (`p/default`) gates every PR on high-confidence findings; CodeQL (`security-extended`) scans Python and TypeScript weekly. Both run in CI with action SHAs pinned. | `.github/workflows/security.yml` | V1 (Secure SDLC) |
| Secrets live in environment variables / CI secrets. `.env*` files are gitignored and absent from history. Example files contain placeholders only. | repo hygiene | V6 (Crypto), V14 |

## Known limitations

- Rate limits are daily quotas, not burst throttles; there is no
  per-second/per-minute window yet.
- Docking and MD routers do not call the rate limiter directly (docking is
  bounded by its exhaustiveness cap; long jobs are queued per user).
- The MD engine uses OpenMM implicit solvent, which approximates explicit
  water and is not suitable for publication-grade free-energy work.
