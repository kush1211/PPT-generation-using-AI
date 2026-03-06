# PPT Genius — AI-Powered Presentation Builder

Generate polished PowerPoint presentations from your data using Google Gemini AI.

## Stack

- **Backend**: Django + Django REST Framework, PostgreSQL
- **Frontend**: React 19 + Vite, Zustand, React Router
- **AI**: Google Gemini 2.5 Flash (`google-genai` SDK)
- **PPT Generation**: python-pptx + Plotly/kaleido (charts as embedded PNGs)

## Setup

### Prerequisites
- Python 3.10+
- Node.js 18+
- PostgreSQL running locally
- Google Gemini API key ([Google AI Studio](https://aistudio.google.com))

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Create `backend/.env`:
```
GEMINI_API_KEY=your_gemini_api_key
SECRET_KEY=your_django_secret_key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

DB_NAME=pptgenius
DB_USER=postgres
DB_PASSWORD=your_postgres_password
DB_HOST=localhost
DB_PORT=5432
```

```bash
python manage.py migrate
python manage.py runserver
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173).

## How It Works

Users progress through 4 steps:

1. **Upload** — Upload a CSV or Excel file (+ optional RFP/requirements doc)
2. **Configure** — Gemini infers presentation objectives from the data; user can edit them
3. **Generate** — Full pipeline runs (~40–60s): Gemini generates slide specs → python-pptx assembles slides → charts rendered as PNGs and embedded
4. **Chat** — Refine slides conversationally

The generated `.pptx` file can be downloaded at any point after generation.
