# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Backend
```bash
cd backend && source venv/bin/activate

python manage.py runserver          # Start Django dev server (port 8000)
python manage.py migrate            # Apply migrations
python manage.py makemigrations     # Create new migrations
python manage.py test api           # Run tests
```

### Frontend
```bash
cd frontend

npm run dev      # Start Vite dev server (port 5173)
npm run build    # Production build
npm run lint     # ESLint
```

## Architecture

### Flow
Users progress through 4 steps: **Upload → Configure → Generate → Chat**

1. Upload CSV/Excel (+ optional RFP doc)
2. Gemini infers objectives from data; user edits them
3. Full generation pipeline runs (~40-60s): Gemini generates slide specs → python-pptx assembles slides → Plotly/kaleido renders charts as PNGs embedded in slides
4. Chat to refine slides conversationally

### Backend (`backend/`)
- **`api/models.py`** — `Project` (UUID PK, status state machine) → `DataFile`, `RFPDocument`, `ObjectivesConfig`, `Insight`, `Slide`, `ChatMessage`
- **`api/views.py`** — All REST endpoints as class-based views
- **`api/services/gemini_client.py`** — Wrapper around `google-genai` SDK (Gemini 2.5 Flash)
- **`api/services/generation/ppt_builder.py`** — python-pptx slide assembly
- **`api/services/generation/chart_builder.py`** — Plotly chart → PNG export via kaleido
- **`core/settings.py`** — Loads all config from `.env`

### Frontend (`frontend/src/`)
- **`App.jsx`** — Router + sidebar with step navigation (steps locked by `project.status`)
- **`store/projectStore.js`** — Zustand global state (projectId, status, slides, etc.)
- **`services/api.js`** — Axios client (base URL: `http://localhost:8000/api`)
- **`components/`** — One component per step: `Upload/`, `Configure/`, `Generate/`, `Chat/`

### API Endpoints (all under `/api/projects/<uuid>/`)
| Method | Path | Purpose |
|--------|------|---------|
| POST | `upload-data/` | Upload CSV/Excel |
| POST | `upload-document/` | Upload RFP/doc (optional) |
| POST | `infer-objectives/` | Gemini extracts objectives from data |
| GET/PUT | `objectives/` | View/edit objectives |
| POST | `generate/` | Run full pipeline (sync) |
| GET | `slides/` | All slides with content |
| GET | `download/` | Stream `.pptx` file |
| GET/POST | `chat/` | Chat history / send message |

### Project Status State Machine
`uploading` → `uploaded` → `configured` → `generating` → `ready` (or `error`)

## Environment
Copy `.env.example` to `.env` in `backend/`. Required variables:
- `GEMINI_API_KEY` — Google AI Studio key
- `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` — PostgreSQL credentials
- `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`
