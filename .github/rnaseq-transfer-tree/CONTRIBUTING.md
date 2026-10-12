# Contributing

## Development setup

**Frontend** (Next.js 14, TypeScript, Tailwind):

```bash
cd bioai-platform/frontend
npm install
npm run dev        # http://localhost:3000
```

**Backend** (FastAPI, Python 3.11+):

```bash
cd bioai-platform/backend
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload # http://localhost:8000
```

Copy `.env.example` to `.env` and fill in Supabase, Redis, and LiteLLM keys.
The app degrades gracefully without optional providers (AI interpretation
shows a visible banner when every model in the fallback chain fails).

## Testing

```bash
# Backend: targeted test files (full suite includes network-dependent tests)
pytest tests/test_docking.py tests/test_auth.py

# Frontend type check
npx tsc --noEmit
```

Docking changes should be validated against the redocking benchmark in
`tmp_redock/redock_benchmark.py` (streptavidin-biotin, PDB 1STP; top pose
RMSD under 2 Å is the bar).

## Conventions

- Keep PRs small and single-purpose.
- Commit messages are short imperative subjects (`fix docking grid parsing`,
  `security: verify JWT signatures`).
- Match existing code style; the backend uses ruff-compatible formatting and
  the frontend follows the Next.js ESLint config.
- Do not commit `.env` files or real credentials. CI runs Semgrep and will
  flag hardcoded secrets.

## Security

See [SECURITY.md](SECURITY.md) for the control model. Report vulnerabilities
privately rather than opening issues.
