# MeetingMind AI — Phase 1 Backend

> FastAPI · Celery · PostgreSQL · Redis · Faster Whisper · Groq LLaMA · ChromaDB

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  Client (Next.js)                                            │
└───────────────────────────┬──────────────────────────────────┘
                            │ HTTPS
┌───────────────────────────▼──────────────────────────────────┐
│  FastAPI (uvicorn/gunicorn)                                  │
│  /api/auth  /api/meetings  /api/ai  /api/reports             │
└──────────┬────────────────────────────────────────┬──────────┘
           │ SQLAlchemy async                        │ Celery task
┌──────────▼──────────┐                  ┌──────────▼──────────┐
│  PostgreSQL 16       │                  │  Celery Worker       │
│  Users, Meetings,    │                  │  ┌────────────────┐  │
│  Transcripts,        │◄─────────────────│  │ 1. FFmpeg      │  │
│  ActionItems,        │  writes result   │  │ 2. Whisper v3  │  │
│  Reports             │                  │  │ 3. Groq LLM    │  │
└─────────────────────┘                  │  │ 4. ChromaDB    │  │
                                         │  └────────────────┘  │
┌─────────────────────┐                  └──────────┬──────────┘
│  Redis               │◄────── broker ─────────────┘
│  Celery broker       │
│  + result backend    │
└─────────────────────┘

┌─────────────────────┐   ┌─────────────────────┐
│  ChromaDB            │   │  Storage (local/S3)  │
│  Transcript embeds   │   │  Audio + Report files│
└─────────────────────┘   └─────────────────────┘
```

---

## Phase 1 AI Pipeline

```
Upload MP4/MP3
     │
     ▼
[Celery Worker]
     │
     ├── FFmpeg → extract 16kHz mono WAV
     │
     ├── Faster Whisper → transcript segments + language detection
     │
     ├── Groq LLaMA 3.3-70B → summary + action items + decisions
     │
     ├── Groq LLaMA 3.3-70B → Minutes of Meeting (Markdown)
     │
     ├── Sentence Transformers → chunk + embed transcript
     │
     └── ChromaDB + PostgreSQL → persist everything
```

---

## Quick Start (Local)

### Prerequisites
- Docker + Docker Compose
- `ffmpeg` (bundled in Docker image)
- Groq API key (free tier available at console.groq.com)

### 1. Clone and configure

```bash
cp .env.example .env
# Edit .env — at minimum set:
#   SECRET_KEY, JWT_SECRET, GROQ_API_KEY
```

### 2. Start all services

```bash
docker compose up --build
```

Services:
| Service | URL |
|---------|-----|
| FastAPI | http://localhost:8000 |
| Swagger UI | http://localhost:8000/api/docs |
| Flower (Celery monitor) | `docker compose --profile debug up` → http://localhost:5555 |
| PostgreSQL | localhost:5432 |
| Redis | localhost:6379 |

### 3. Run without Docker (dev)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

# Terminal 1 – API
uvicorn main:app --reload --port 8000

# Terminal 2 – Celery worker
celery -A workers.celery_app worker --queues ai,reports --concurrency 1 --loglevel info

# Terminal 3 – Flower (optional)
celery -A workers.celery_app flower
```

---

## API Reference

### Auth

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/register` | Register + create workspace |
| POST | `/api/auth/login` | Login → access + refresh tokens |
| POST | `/api/auth/refresh` | Rotate refresh token |
| POST | `/api/auth/logout` | Revoke refresh token |
| GET  | `/api/auth/me` | Current user info |

**Register example:**
```json
POST /api/auth/register
{
  "name": "Devidas K.",
  "email": "devidas@hkbk.edu",
  "password": "securepassword",
  "workspace": {
    "name": "HKBK Engineering",
    "slug": "hkbk-engineering"
  }
}
```

---

### Meetings

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/meetings` | List all meetings (paginated) |
| POST | `/api/meetings/upload` | Upload audio/video file (multipart) |
| GET | `/api/meetings/{id}` | Full meeting detail with transcript |
| GET | `/api/meetings/{id}/status` | Live processing status |
| PATCH | `/api/meetings/{id}` | Update title |
| DELETE | `/api/meetings/{id}` | Delete + clean storage |

**Upload example:**
```bash
curl -X POST http://localhost:8000/api/meetings/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@meeting.mp4" \
  -F "title=Q4 Budget Review"
```

**Status polling:**
```json
GET /api/meetings/{id}/status
{
  "meeting_id": "...",
  "status": "transcribing",
  "progress_percent": 50,
  "current_step": "transcribing"
}
```

---

### AI

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/ai/chat` | RAG-powered meeting Q&A |
| POST | `/api/ai/summarize` | (Re-)generate summary + action items |
| POST | `/api/ai/generate-mom` | (Re-)generate Minutes of Meeting |

**Chat example:**
```json
POST /api/ai/chat
{
  "question": "What decisions were made about the infrastructure upgrade?",
  "meeting_ids": ["uuid-of-specific-meeting"],
  "top_k": 5
}
```

---

### Reports

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/reports/{id}/generate` | Queue async report generation |
| GET | `/api/reports/{id}/download?fmt=pdf` | Download PDF/DOCX/TXT/MD |

---

## Environment Variables

See `.env.example` for full reference. Critical ones:

| Variable | Description |
|----------|-------------|
| `SECRET_KEY` | App secret (any long random string) |
| `JWT_SECRET` | JWT signing key (different from SECRET_KEY) |
| `GROQ_API_KEY` | From console.groq.com (free) |
| `DATABASE_URL` | `postgresql+asyncpg://user:pass@host/db` |
| `WHISPER_MODEL_SIZE` | `large-v3` for best accuracy, `medium` for speed |
| `WHISPER_DEVICE` | `cpu` or `cuda` |
| `STORAGE_BACKEND` | `local`, `s3`, or `r2` |

---

## Database Migrations (Production)

```bash
# Create new migration after model changes
alembic revision --autogenerate -m "add speaker_language column"

# Apply migrations
alembic upgrade head

# Rollback one step
alembic downgrade -1
```

---

## Project Structure

```
meetingmind-backend/
├── main.py                        # FastAPI app factory
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env.example
│
├── config/
│   └── settings.py                # Pydantic settings (all env vars)
│
├── db/
│   ├── database.py                # Async SQLAlchemy engine + session
│   └── migrations/env.py          # Alembic async env
│
├── models/
│   ├── orm.py                     # SQLAlchemy ORM models
│   └── schemas.py                 # Pydantic request/response schemas
│
├── api/
│   ├── deps.py                    # FastAPI dependencies (auth, DB)
│   ├── middleware/logging.py      # Request logging middleware
│   └── routes/
│       ├── auth.py                # Register, login, refresh, logout
│       ├── meetings.py            # Upload, list, detail, status, delete
│       ├── ai.py                  # Chat (RAG), summarize, MoM
│       └── reports.py             # PDF/DOCX/TXT download
│
├── ai/
│   ├── transcription/
│   │   ├── ffmpeg.py              # Audio extraction
│   │   └── whisper.py             # Faster Whisper transcription
│   ├── summarization/
│   │   └── groq_llm.py            # Summary + MoM via Groq LLaMA
│   ├── embeddings/
│   │   └── chroma.py              # ChromaDB embed + RAG retrieval
│   └── chat/
│       └── rag_chat.py            # Full RAG pipeline
│
├── services/
│   ├── auth.py                    # JWT + password hashing
│   ├── storage.py                 # Local/S3/R2 abstraction
│   └── report_generator.py        # PDF (ReportLab) + DOCX generation
│
├── workers/
│   ├── celery_app.py              # Celery configuration
│   └── tasks.py                  # process_meeting + generate_report tasks
│
└── utils/
    ├── slugify.py
    └── time_fmt.py
```

---

## Phase 2 Additions (next)

- `ai/diarization/pyannote.py` — speaker diarization (SPEAKER_00, SPEAKER_01...)
- `api/routes/team.py` — workspace member management
- `api/routes/analytics.py` — talk time, participation stats
- RAG chat streaming via SSE

## Phase 3 Additions

- `ai/face_recognition/insightface.py` — face detection + identity matching
- Face embedding storage in Participant table

## Phase 4 Additions

- `api/routes/integrations.py` — Zoom webhook + Google Meet Playwright bot
- Real-time transcription via WebSocket

---

## Production Checklist

- [ ] Set `APP_ENV=production` (disables Swagger UI)
- [ ] Use strong random `SECRET_KEY` and `JWT_SECRET`
- [ ] Set `STORAGE_BACKEND=s3` or `r2`
- [ ] Run `alembic upgrade head` before starting API
- [ ] Use Gunicorn (see commented CMD in Dockerfile)
- [ ] Set up NGINX reverse proxy with HTTPS
- [ ] Configure log aggregation (Loki / CloudWatch)
- [ ] Set `WHISPER_DEVICE=cuda` if GPU available (3–4× faster)
