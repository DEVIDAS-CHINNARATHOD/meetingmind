# MeetingMind AI

> **AI-powered meeting intelligence platform** — transcription, speaker diarization, face recognition, RAG chat, Zoom/Meet bots, real-time WebSocket transcription, and a full Next.js 15 dashboard.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│  Browser / Mobile                                               │
│  Next.js 15 · TypeScript · Tailwind · Framer Motion            │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTPS / WSS
              ┌─────────────▼──────────────┐
              │         NGINX              │
              │  SSL termination · Routing │
              └──────┬──────────┬──────────┘
                     │          │
         ┌───────────▼──┐  ┌───▼────────────────────┐
         │  FastAPI      │  │  Next.js Server         │
         │  :8000        │  │  :3000                  │
         │               │  └─────────────────────────┘
         │  /api/*       │
         │  /ws/*        │
         └──────┬────────┘
                │
     ┌──────────┼──────────────────────┐
     │          │                      │
┌────▼────┐ ┌──▼───┐  ┌─────────────────────────────────┐
│PostgreSQL│ │Redis │  │  Celery Workers (3 queues)      │
│:5432     │ │:6379 │  │                                 │
└─────────┘ └──────┘  │  ai queue:                      │
                       │    process_meeting               │
                       │    face_recognition              │
                       │    rename_speaker                │
                       │    finalize_live_meeting         │
                       │                                 │
                       │  reports queue:                 │
                       │    generate_report (PDF/DOCX)   │
                       │                                 │
                       │  bots queue:                    │
                       │    join_zoom_meeting             │
                       │    join_google_meet              │
                       └─────────────────────────────────┘
                                      │
             ┌────────────────────────┼─────────────────────┐
             │                        │                     │
      ┌──────▼──────┐        ┌────────▼──────┐    ┌────────▼──────┐
      │  ChromaDB   │        │  File Storage  │    │  InsightFace  │
      │  Embeddings │        │  local/S3/R2   │    │  Face models  │
      └─────────────┘        └───────────────┘    └───────────────┘
```

---

## Phase Summary

| Phase | Features |
|-------|----------|
| **Phase 1** | Upload → FFmpeg → Faster Whisper → Groq LLaMA summary → MoM → ChromaDB embeds |
| **Phase 2** | Pyannote diarization · Speaker stats · SSE streaming chat · Analytics · Team management · Hybrid search |
| **Phase 3** | InsightFace face detection · ArcFace embeddings · Identity DB · Speaker→identity mapping |
| **Phase 4** | Zoom SDK bot · Google Meet Playwright bot · WebSocket real-time transcription · Integrations API |

---

## Quick Start (Docker — recommended)

### Prerequisites
- Docker ≥ 24 and Docker Compose ≥ 2.20
- 8 GB RAM recommended (Whisper large-v3 needs ~3 GB)

### 1 — Environment setup

```bash
make setup
```

This copies `.env.example` files. Then fill in the required values:

**`backend/.env`** — minimum required:
```env
SECRET_KEY=your-long-random-secret-here
JWT_SECRET=another-long-random-secret
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxx   # free at console.groq.com
DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/meetingmind
```

**`frontend/.env.local`** — minimum required:
```env
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_xxxx   # from dashboard.clerk.com
CLERK_SECRET_KEY=sk_test_xxxx
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### 2 — Start everything

```bash
docker compose up --build
```

| Service | URL |
|---------|-----|
| **Frontend** | http://localhost:3000 |
| **Backend API** | http://localhost:8000 |
| **Swagger UI** | http://localhost:8000/api/docs |
| **Flower (workers)** | `docker compose --profile debug up` → http://localhost:5555 |

### 3 — First use

1. Open http://localhost:3000 → Sign up
2. Go to **Upload** → drag a `.mp4` or `.mp3` file
3. Watch the pipeline animate in real time
4. When complete, click **View** to see transcript + MoM + action items
5. Open **AI Chat** → ask questions about your meeting

---

## Local Development (no Docker)

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill in keys

# Terminal 1 — API
uvicorn main:app --reload --port 8000

# Terminal 2 — AI worker
celery -A workers.celery_app worker --queues ai --concurrency 1 --loglevel info

# Terminal 3 — Reports worker (optional)
celery -A workers.celery_app worker --queues reports --concurrency 4 --loglevel info
```

Requires: PostgreSQL on :5432, Redis on :6379, ffmpeg in PATH.

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local   # fill in Clerk keys
npm run dev
```

---

## Project Structure

```
meetingmind/
├── docker-compose.yml          ← Full-stack orchestration (all 6 services)
├── nginx.conf                  ← Production reverse proxy
├── Makefile                    ← Handy dev shortcuts
├── .gitignore
│
├── backend/                    ← FastAPI + Celery Python backend
│   ├── main.py                 ← App factory (all routes registered)
│   ├── requirements.txt
│   ├── Dockerfile              ← Multi-stage: api / worker
│   ├── Dockerfile.bots         ← Playwright + Chromium for bot worker
│   ├── .env.example
│   │
│   ├── config/settings.py      ← Pydantic settings (all env vars)
│   ├── db/
│   │   ├── database.py         ← Async SQLAlchemy engine + session
│   │   └── migrations/         ← Alembic migrations (4 versions)
│   ├── models/
│   │   ├── orm.py              ← 8 SQLAlchemy ORM models
│   │   └── schemas.py          ← Pydantic v2 request/response schemas
│   │
│   ├── api/
│   │   ├── deps.py             ← Auth dependencies, role guards
│   │   ├── middleware/         ← Request logging, Redis rate limiter
│   │   └── routes/             ← 13 route modules (all phases)
│   │       ├── auth.py
│   │       ├── meetings.py
│   │       ├── ai.py           ← summarize, generate-mom
│   │       ├── ai_stream.py    ← SSE streaming chat
│   │       ├── reports.py
│   │       ├── analytics.py
│   │       ├── team.py
│   │       ├── action_items.py
│   │       ├── speakers.py
│   │       ├── search.py       ← Hybrid text + vector search
│   │       ├── identities.py   ← Face recognition enrollment
│   │       ├── integrations.py ← Zoom + Meet bots
│   │       └── websocket.py    ← Real-time transcription WS
│   │
│   ├── ai/
│   │   ├── transcription/      ← FFmpeg + Faster Whisper
│   │   ├── diarization/        ← Pyannote.audio
│   │   ├── summarization/      ← Groq LLaMA (summary + MoM)
│   │   ├── embeddings/         ← Sentence Transformers + ChromaDB
│   │   ├── face_recognition/   ← InsightFace detector + identity DB
│   │   ├── chat/               ← RAG pipeline
│   │   └── realtime/           ← Streaming transcriber (chunked)
│   │
│   ├── bots/
│   │   ├── zoom/zoom_bot.py    ← Zoom SDK integration
│   │   └── meet/meet_bot.py    ← Playwright browser bot
│   │
│   ├── workers/
│   │   ├── celery_app.py       ← 3-queue Celery config
│   │   ├── tasks.py            ← Main pipeline (Phases 1-2)
│   │   ├── face_tasks.py       ← Face recognition tasks (Phase 3)
│   │   └── bot_tasks.py        ← Bot + live meeting tasks (Phase 4)
│   │
│   ├── services/
│   │   ├── auth.py             ← JWT + bcrypt
│   │   ├── storage.py          ← Local/S3/R2 abstraction
│   │   └── report_generator.py ← PDF (ReportLab) + DOCX
│   │
│   └── tests/                  ← 60+ unit + integration tests
│
└── frontend/                   ← Next.js 15 TypeScript frontend
    ├── src/
    │   ├── app/                ← App Router pages (12 routes)
    │   │   ├── dashboard/
    │   │   ├── meetings/[id]/
    │   │   ├── meetings/upload/
    │   │   ├── chat/           ← SSE streaming AI chat
    │   │   ├── analytics/
    │   │   ├── reports/
    │   │   ├── team/
    │   │   ├── integrations/
    │   │   └── settings/
    │   │
    │   ├── components/
    │   │   ├── layout/         ← Sidebar, Topbar, Providers
    │   │   ├── ui/             ← Primitives, SearchCommand (Cmd+K)
    │   │   ├── meetings/       ← MeetingCard, ProcessingPipeline
    │   │   └── dashboard/      ← StatCard
    │   │
    │   ├── hooks/
    │   │   ├── use-meeting-poller.ts  ← 4s status polling
    │   │   ├── use-ws-transcribe.ts   ← WebSocket PCM streaming
    │   │   └── use-search.ts          ← Debounced hybrid search
    │   │
    │   ├── services/           ← Full typed API layer (all endpoints)
    │   ├── stores/             ← Zustand (meetings, chat, UI)
    │   ├── types/              ← Full TypeScript interfaces
    │   └── lib/                ← utils, nanoid
    │
    ├── package.json
    ├── tailwind.config.ts
    ├── Dockerfile.frontend
    └── .env.example
```

---

## Backend API Reference

### Base URL: `http://localhost:8000/api`

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/register` | Register + create workspace |
| POST | `/auth/login` | Login → JWT tokens |
| POST | `/auth/refresh` | Rotate refresh token |
| GET  | `/auth/me` | Current user |
| GET  | `/meetings` | List meetings (paginated) |
| POST | `/meetings/upload` | Upload audio/video |
| GET  | `/meetings/:id` | Meeting detail + transcript |
| GET  | `/meetings/:id/status` | Processing status (poll) |
| DELETE | `/meetings/:id` | Delete + clean storage |
| POST | `/ai/chat` | RAG chat (non-streaming) |
| POST | `/ai/chat/stream` | SSE streaming chat |
| POST | `/ai/summarize` | (Re-)generate summary |
| POST | `/ai/generate-mom` | (Re-)generate MoM |
| GET  | `/analytics/overview` | Workspace KPIs |
| GET  | `/analytics/speakers` | Workspace speaker stats |
| GET  | `/analytics/meeting-frequency` | Daily meeting counts |
| GET  | `/reports/:id/download` | Download PDF/DOCX/TXT |
| GET  | `/team/members` | List team members |
| POST | `/team/invite` | Invite a member |
| GET  | `/search?q=` | Hybrid semantic + text search |
| GET  | `/identities` | List enrolled faces |
| POST | `/identities/enroll` | Enroll face from photo |
| POST | `/integrations/zoom/join` | Dispatch Zoom bot |
| POST | `/integrations/meet/join` | Dispatch Meet bot |
| GET  | `/integrations/status` | Active bot sessions |
| WS   | `/ws/transcribe` | Real-time PCM transcription |

Full interactive docs: http://localhost:8000/api/docs

---

## Key Configuration

### Enable Speaker Diarization (Phase 2)
```env
HUGGINGFACE_TOKEN=hf_xxxxxxxxxxxx
DIARIZATION_ENABLED=true
```
Accept licenses at:
- https://huggingface.co/pyannote/speaker-diarization-3.1
- https://huggingface.co/pyannote/segmentation-3.0

### Enable Face Recognition (Phase 3)
```bash
pip install insightface onnxruntime opencv-python-headless
# InsightFace buffalo_l downloads automatically on first run (~300MB)
```

### Enable Zoom Bot (Phase 4)
```env
ZOOM_CLIENT_ID=your_zoom_client_id
ZOOM_CLIENT_SECRET=your_zoom_client_secret
ZOOM_ACCOUNT_ID=your_zoom_account_id
```
Register at https://marketplace.zoom.us → Server-to-Server OAuth

### Switch to S3/R2 Storage
```env
STORAGE_BACKEND=s3
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_BUCKET_NAME=meetingmind-uploads
AWS_REGION=ap-south-1
```

---

## Production Deployment

### Vercel + Railway/Render

```bash
# Frontend → Vercel
cd frontend && vercel --prod

# Backend → Railway
railway up
```

### Full Docker Production

```bash
# 1. Point nginx.conf server_name to your domain
# 2. Add SSL certs to ./ssl/

make prod
# Starts: postgres, redis, api, 3x workers, frontend, nginx
```

### Database Migrations

```bash
# Run pending migrations
make migrate

# Create new migration
make migrate-new MSG="add column xyz"
```

---

## Production Checklist

**Backend:**
- [ ] `SECRET_KEY` and `JWT_SECRET` are long random strings
- [ ] `APP_ENV=production` (disables Swagger UI)
- [ ] `GROQ_API_KEY` is set
- [ ] `STORAGE_BACKEND=s3` or `r2` (not local)
- [ ] Run `make migrate` before first start
- [ ] `ALLOWED_ORIGINS` includes your frontend domain

**Frontend:**
- [ ] Clerk production keys (not test keys)
- [ ] `NEXT_PUBLIC_API_URL` points to production backend
- [ ] `npm run build` succeeds with zero errors
- [ ] `npm run type-check` passes

**Infrastructure:**
- [ ] SSL certificates in `./ssl/`
- [ ] NGINX `server_name` updated
- [ ] Docker volumes backed up (postgres_data, app_data)
- [ ] Monitoring set up (Flower at :5555 or external)

---

## Tech Stack Summary

**Backend:** Python 3.12 · FastAPI · SQLAlchemy 2 (async) · Alembic · Celery · Redis · PostgreSQL · Faster Whisper · Pyannote.audio · InsightFace · Groq LLaMA 3.3-70B · LangChain · ChromaDB · Sentence Transformers · ReportLab · python-docx · Playwright · FFmpeg

**Frontend:** Next.js 15 · React 19 · TypeScript · Tailwind CSS · Clerk · TanStack Query · Zustand · Framer Motion · Recharts · Lucide React · Sonner · React Dropzone · React Hook Form · Zod

**Infrastructure:** Docker · Docker Compose · NGINX · Redis · PostgreSQL 16 · Xvfb (bots)
