# Section - Land Graph Operating Layer

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

## Documentation

- **DEMO_SCRIPT.md** — Full narrative script for the 5-7 minute pitch
- **DEMO_CHECKLIST.md** — Pre-demo checks, Q&A prep, contingencies
- **.taskmaster/docs/prd.txt** — Complete product requirements document with phases A-F

## License

Proprietary. Compass Operating LLC + Investors.
