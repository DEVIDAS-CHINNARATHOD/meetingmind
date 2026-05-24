# MeetingMind AI — Frontend

> Next.js 15 · TypeScript · Tailwind CSS · Clerk Auth · TanStack Query · Zustand · Framer Motion

---

## Stack

| Layer           | Tech                              |
|-----------------|-----------------------------------|
| Framework       | Next.js 15 App Router             |
| Language        | TypeScript (strict)               |
| Styling         | Tailwind CSS + custom design tokens |
| Auth            | Clerk                             |
| State           | Zustand (global) + TanStack Query (server) |
| Animations      | Framer Motion                     |
| Icons           | Lucide React                      |
| Charts          | Recharts                          |
| Forms           | React Hook Form + Zod             |
| File upload     | React Dropzone                    |
| Notifications   | Sonner                            |

---

## Quick Start

### 1. Install

```bash
cd meetingmind-frontend
npm install
```

### 2. Configure environment

```bash
cp .env.example .env.local
# Fill in:
#   NEXT_PUBLIC_API_URL          → your backend URL (default: http://localhost:8000)
#   NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY
#   CLERK_SECRET_KEY
```

Get Clerk keys at [dashboard.clerk.com](https://dashboard.clerk.com).

### 3. Run

```bash
npm run dev       # development with Turbopack
npm run build     # production build
npm run start     # serve production build
```

Open [http://localhost:3000](http://localhost:3000)

---

## Project Structure

```
src/
├── app/                      # Next.js App Router pages
│   ├── layout.tsx            # Root layout (fonts, Clerk, providers)
│   ├── page.tsx              # → redirects to /dashboard
│   ├── auth/
│   │   ├── login/page.tsx    # Clerk SignIn
│   │   └── register/page.tsx # Clerk SignUp
│   ├── dashboard/page.tsx    # Dashboard overview
│   ├── meetings/
│   │   ├── page.tsx          # Meetings list
│   │   ├── [id]/page.tsx     # Meeting detail (transcript, MoM, actions)
│   │   └── upload/page.tsx   # Upload + bot join
│   ├── chat/page.tsx         # Streaming AI chat (RAG)
│   ├── analytics/page.tsx    # Charts + KPIs
│   ├── reports/page.tsx      # PDF/DOCX downloads
│   ├── team/page.tsx         # Member management
│   ├── integrations/page.tsx # Zoom + Meet bots
│   └── settings/page.tsx     # Profile, API keys, AI config
│
├── components/
│   ├── layout/
│   │   ├── sidebar.tsx       # Navigation sidebar
│   │   ├── topbar.tsx        # Search bar + notifications
│   │   └── providers.tsx     # QueryClient + SearchCommand
│   ├── ui/
│   │   ├── primitives.tsx    # Button, Card, Badge, Input, Progress, Skeleton…
│   │   └── search-command.tsx# Cmd+K global search overlay
│   ├── meetings/
│   │   ├── meeting-card.tsx  # Meeting card (grid/list)
│   │   └── processing-pipeline.tsx # AI pipeline progress
│   └── dashboard/
│       └── stat-card.tsx     # KPI stat cards
│
├── hooks/
│   ├── use-meeting-poller.ts # Polls /status every 4s during processing
│   ├── use-ws-transcribe.ts  # WebSocket real-time transcription
│   └── use-search.ts         # Debounced hybrid search
│
├── services/
│   ├── api-client.ts         # Axios + JWT interceptor + refresh
│   └── index.ts              # All API service functions
│
├── stores/
│   └── meeting-store.ts      # Zustand: meetings, chat, UI state
│
├── types/
│   └── index.ts              # Full TypeScript interfaces
│
└── lib/
    ├── utils.ts              # cn(), formatters, color helpers
    └── nanoid.ts             # Lightweight ID generator
```

---

## Key Features

### Global Search (Cmd+K)
Press `⌘K` anywhere to open the command palette. Runs hybrid semantic + full-text search across all meeting transcripts.

### Real-time AI Chat
The chat page streams tokens from Groq LLaMA 3.3-70B via SSE. Select specific meetings as context or search all. Displays source citations with timestamp links.

### Meeting Processing
Upload → file goes to FastAPI backend → Celery pipeline runs in background → frontend polls `/meetings/:id/status` every 4s → progress bar updates in real time.

### Bot Integration
POST to `/integrations/zoom/join` or `/integrations/meet/join` to dispatch a Celery bot task. The Integrations page shows live bot session status with stop control.

---

## Deployment

### Vercel (recommended)

```bash
npm install -g vercel
vercel --prod
```

Set these in Vercel dashboard → Environment Variables:
- `NEXT_PUBLIC_API_URL` → your Railway/Render backend URL
- `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`
- `CLERK_SECRET_KEY`

### Docker

```dockerfile
FROM node:20-alpine AS deps
WORKDIR /app
COPY package*.json ./
RUN npm ci

FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./package.json
EXPOSE 3000
CMD ["npm", "start"]
```

---

## Design System

All design tokens live in `tailwind.config.ts` and `globals.css`.

| Token             | Value                        |
|-------------------|------------------------------|
| Primary color     | `hsl(263 80% 62%)` — violet  |
| Background        | `hsl(224 30% 6%)` — near-black |
| Card surface      | `hsl(225 28% 9%)`            |
| Border            | `hsl(224 22% 16%)`           |
| Font (display)    | Syne (headings)              |
| Font (body)       | DM Sans                      |
| Font (mono)       | JetBrains Mono               |

Custom utilities: `.text-gradient`, `.glass`, `.glass-strong`, `.glow-violet`, `.skeleton`, `.wave-bar`, `.surface-card`, `.btn-gradient`

---

## Backend Connection

The frontend expects the FastAPI backend at `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`).

All requests include a JWT Bearer token stored in `localStorage` under `mm_access_token`. The Axios interceptor auto-refreshes tokens using the refresh token at `mm_refresh_token`.

**CORS:** Ensure `ALLOWED_ORIGINS=http://localhost:3000` is set in the backend `.env`.

---

## Production Checklist

- [ ] Set all Clerk environment variables
- [ ] Set `NEXT_PUBLIC_API_URL` to production backend
- [ ] Ensure backend `ALLOWED_ORIGINS` includes frontend domain
- [ ] Run `npm run type-check` — zero errors
- [ ] Run `npm run build` — successful
- [ ] Test auth flow (login → dashboard → logout)
- [ ] Test file upload with a short MP4
- [ ] Test AI chat response
