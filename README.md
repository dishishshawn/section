# Section - Land Graph Operating Layer

[![CI](https://github.com/OWNER/REPO/actions/workflows/ci.yml/badge.svg)](https://github.com/OWNER/REPO/actions/workflows/ci.yml)

AI-native platform for land services firms that turns documents (deeds, leases, probates, assignments) into a structured, queryable Land Graph. Every landman deliverable (ownership reports, runsheets, leasehold confirmations, curative packages, A&D memos) becomes a view or export from that single model.

## Quick Start

### Prerequisites
- Node.js 18+
- Python 3.10+
- Docker + Docker Compose (for Postgres)

### Development Setup

```bash
# Clone repo
git clone <repo>
cd section

# Backend setup
cd backend
python -m venv venv
source venv/Scripts/activate  # Windows
pip install -r requirements.txt

# Frontend setup
cd ../frontend
npm install

# Start Postgres (from project root)
docker-compose up -d

# In backend venv, seed demo data
python backend/demo_seed.py

# Run backend (from backend dir)
python main.py  # runs on localhost:8000

# In another terminal, run frontend (from frontend dir)
npm run dev  # runs on localhost:3000
```

Then visit http://localhost:3000 in your browser.

## Architecture

### Frontend (Next.js + Tailwind)
- **ProjectShell:** Create and list projects
- **ProjectDetail:** Navigate between views (Runsheet, Ownership, Calendar, Risk Dashboard)
- **Views:** Each view reads from the Land Graph and renders a focused perspective
- **Exports:** PDF generation using ReportLab

### Backend (FastAPI + SQLAlchemy + Postgres)
- **REST API:** Projects, documents, extraction, ownership queries, exports
- **Extractors:** Lease and deed extractors using Claude API for structured extraction
- **Land Graph Schema:** Tracts, parties, instruments, interests, obligations
- **Database:** Postgres with pgvector for semantic search over documents

### Database (Postgres)
- `projects` — project metadata (name, jurisdiction, owner_org)
- `documents` — source files (S3 key, extraction status)
- `tracts` — surface/mineral acreage in scope
- `parties` — individuals, estates, entities holding interests
- `instruments` — deeds, leases, assignments, probates, etc.
- `interests` — fractional ownership with burdens
- `obligations` — primary term, Pugh triggers, shut-in clocks, rental payments

## Project Structure

```
section/
├── frontend/                 # Next.js app
│   ├── app/
│   │   ├── components/      # React components (ProjectShell, views, exports)
│   │   ├── page.tsx         # Main entry
│   │   └── api/             # Backend proxies
│   ├── package.json
│   └── tsconfig.json
├── backend/                 # FastAPI + SQLAlchemy
│   ├── main.py             # App entry, middleware, routes
│   ├── database.py         # SQLAlchemy engine, session
│   ├── models.py           # Land Graph schema
│   ├── routes.py           # API endpoints
│   ├── extractors.py       # Claude-powered extraction
│   ├── exports.py          # PDF generation
│   ├── demo_seed.py        # Demo data seeding
│   ├── requirements.txt
│   └── Dockerfile
├── docker-compose.yml       # Postgres + pgvector
├── DEMO_SCRIPT.md          # 5-7 minute demo narrative
├── DEMO_CHECKLIST.md       # Dry run & QA checklist
└── .taskmaster/            # Task management
    ├── docs/
    │   └── prd.txt        # Full product requirements document
    └── state.json
```

## Email Setup

Section uses [Resend](https://resend.com) for transactional email (magic-link sign-in).

### Required environment variables

| Variable | Description | Example |
|---|---|---|
| `RESEND_API_KEY` | Resend API key (starts `re_`) | `re_live_abc123` |
| `FROM_EMAIL` | Verified sender address | `noreply@yourdomain.com` |
| `REPLY_TO_EMAIL` | Reply-To / unsubscribe address | `no-reply@yourdomain.com` |

Without `RESEND_API_KEY` the server prints magic links to stdout (dev mode).

### DNS records required

Before sending from a custom domain, add these records to your DNS:

**SPF** (add to an existing TXT record or create new):
```
yourdomain.com.  TXT  "v=spf1 include:amazonses.com ~all"
```
*(Resend routes via Amazon SES — use `include:amazonses.com`. Check [Resend docs](https://resend.com/docs/dashboard/domains/introduction) for the current value.)*

**DKIM** — Resend provides three CNAME records per domain (find them under *Domains* in the Resend dashboard):
```
resend._domainkey.yourdomain.com.  CNAME  <value-from-resend>
```

**DMARC** — start with `p=none` while you verify, then tighten:
```
_dmarc.yourdomain.com.  TXT  "v=DMARC1; p=quarantine; rua=mailto:dmarc-reports@yourdomain.com; ruf=mailto:dmarc-reports@yourdomain.com; pct=100"
```

### Verifying DNS propagation

```bash
# SPF
dig TXT yourdomain.com +short

# DKIM (replace token with the one Resend gives you)
dig TXT resend._domainkey.yourdomain.com +short

# DMARC
dig TXT _dmarc.yourdomain.com +short
```

Each should return the record you added. Allow up to 48 hours for global propagation. The Resend dashboard shows a green checkmark once it detects all records.

---

## Running the Demo

1. Start Postgres: `docker-compose up -d`
2. Seed data: `python backend/demo_seed.py`
3. Start backend: `python main.py` (backend dir)
4. Start frontend: `npm run dev` (frontend dir)
5. Open http://localhost:3000
6. Click "Garfield County 640 - STACK Area" to load the demo project
7. Navigate between views: Runsheet → Ownership → Obligations → Risk Dashboard
8. Click "📄 Export Report" to generate a PDF ownership report

## Demo Views

### Runsheet
Chain of title with gaps and curative needs highlighted in red.

### Ownership
Fractional ownership waterfall, pie chart, acreage summary.

### Obligations Calendar
Dated obligations (primary term, Pugh triggers, shut-in clocks, rental payments) with color-coded priority alerts.

### Risk Dashboard
Portfolio-level view: lease expirations, royalty ranges, flagged issues (title defects, at-risk leases, ORRI burdens).

### PDF Export
Ownership report rendered in Compass's template. All fields auto-populated from the Land Graph.

## API Endpoints

### Projects
- `POST /api/projects` — Create project
- `GET /api/projects` — List projects
- `GET /api/projects/{id}` — Get project

### Documents
- `POST /api/projects/{id}/documents` — Upload document
- `GET /api/projects/{id}/documents` — List documents
- `POST /api/projects/{id}/extract` — Extract from document

### Ownership & Obligations
- `GET /api/projects/{id}/ownership` — Get fractional ownership
- `GET /api/projects/{id}/obligations` — Get all obligations

### Exports
- `GET /api/projects/{id}/export/ownership` — Generate ownership report PDF

## Next Steps

1. **Database connection:** Postgres must be running (docker-compose) for demo data seeding
2. **Live extraction:** Upload real documents to trigger Claude extraction
3. **Template customization:** Modify PDF export to match customer templates
4. **Multi-jurisdiction:** Add Texas and New Mexico extractors + templates
5. **Deployment:** Deploy frontend to Vercel, backend to Railway/Render, DB to hosted Postgres

## Tech Stack

- **Frontend:** Next.js, TypeScript, Tailwind, Axios
- **Backend:** FastAPI, SQLAlchemy, Pydantic
- **Database:** Postgres + pgvector
- **AI:** Claude API (Anthropic SDK)
- **PDF:** ReportLab
- **Deployment:** Docker, Docker Compose

## Running tests

Backend (pytest + httpx TestClient, in-memory SQLite):

```bash
cd backend
venv/Scripts/python -m pytest                     # run all tests
venv/Scripts/python -m pytest --cov=. --cov-report=term   # with coverage
```

Target is >=60% coverage on the auth/org/billing/override/route modules.

Frontend unit tests (vitest + React Testing Library, jsdom):

```bash
cd frontend
npm install          # one-time
npx vitest run       # or: npm test
```

Frontend e2e smoke (Playwright — requires backend+frontend running):

```bash
cd frontend
SECTION_SESSION_COOKIE=<paste-cookie> npx playwright test
```

## Continuous Integration

GitHub Actions runs on every pull request and on pushes to `main` (`.github/workflows/ci.yml`). Three parallel jobs enforce pre-merge gates: a **backend** job (Python 3.11, `pytest` with `--cov-fail-under=60`), a **lint** job (`ruff check` + `black --check` on `backend/`), and a **frontend** job (Node 20, `npm run typecheck`, `npm run lint` if present, `npm run test` via Vitest, and `npm run build`). External services (Stripe, Resend, Anthropic) are never called — the workflow injects dummy values for `SECRET_KEY`, `STRIPE_API_KEY`, `STRIPE_WEBHOOK_SECRET`, `RESEND_API_KEY`, and `ANTHROPIC_API_KEY`, and the test suite mocks the SDKs. Playwright e2e is gated and does not run in CI.

To require green checks before merge, enable **branch protection** on `main` in GitHub (Settings → Branches → Add rule): check "Require status checks to pass before merging" and select `Backend (pytest + coverage)`, `Lint (ruff + black)`, and `Frontend (typecheck + test + build)` as required checks. See the [GitHub docs on protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches). Replace `OWNER/REPO` in the status badge at the top of this README with the actual GitHub path once the repo is pushed.

## Observability

**Structured logging.** The backend uses stdlib `logging` with a minimal JSON formatter (`backend/logging_config.py`). Every log line is a JSON object with `time`, `level`, `logger`, `message`, and — when inside an HTTP request — `request_id`, `user_id`, and `route`. Call `setup_logging()` once at startup (already wired in `main.py`). Use `logger = get_logger(__name__)` in new modules; avoid `print()` in request-path code.

**Request IDs.** `RequestIDMiddleware` (`backend/middleware.py`) reads an incoming `X-Request-ID` header if the client supplied a UUID, otherwise mints a fresh UUID4. The id is stored in a `contextvar` so every log record emitted during the request carries it, and is echoed back in the `X-Request-ID` response header so proxies and frontend traces can correlate.

**Sentry (backend).** Set `SENTRY_DSN` in the deploy environment to turn on error reporting. Optional env vars: `GIT_SHA` (release tag), `ENV`, `SENTRY_TRACES_SAMPLE_RATE` (default 0.1). With no DSN, `sentry_sdk.init` is skipped entirely — dev and tests are safe no-ops. PII is off by default.

**Sentry (frontend).** Frontend integration lives in `frontend/app/sentry.config.ts` and is wired in `frontend/next.config.ts` via `withSentryConfig`. Gated on `NEXT_PUBLIC_SENTRY_DSN`. Note: `@sentry/nextjs` v8 declares a peer dep of Next 13/14/15; this repo pins Next 16, so `@sentry/nextjs` is declared as an **optional** dependency and loaded dynamically. If npm install fails on the Sentry package it is skipped; the app still builds. Workaround until `@sentry/nextjs` v9 lands with Next 16 support: either pin Next to 15.x, or upload source maps manually via the `sentry-cli` in CI.

**Secrets.** Never commit DSNs or auth tokens. `SENTRY_DSN`, `SENTRY_AUTH_TOKEN`, `SENTRY_ORG`, and `SENTRY_PROJECT` are read from the environment only.

## Documentation

- **DEMO_SCRIPT.md** — Full narrative script for the 5-7 minute pitch
- **DEMO_CHECKLIST.md** — Pre-demo checks, Q&A prep, contingencies
- **.taskmaster/docs/prd.txt** — Complete product requirements document with phases A-F

## License

Proprietary. Compass Operating LLC + Investors.
