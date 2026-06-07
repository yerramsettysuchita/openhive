# OpenHive Dashboard

A single-page Next.js dashboard for OpenHive. It reads directly from the
Supabase `agent_verdicts` table (anon key) and shows the live repository health
score, the agent activity feed, the Transparent Disagreement Protocol log, and
the daily digest archive. No mock data — everything is real swarm output.

## Deploy to Vercel (2 minutes)

1. Go to **vercel.com** → **Add New… → Project** → import `yerramsettysuchita/openhive`.
2. Set **Root Directory** to `frontend`.
3. Add **Environment Variables**:
   - `NEXT_PUBLIC_SUPABASE_URL` — your Supabase project URL
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY` — your Supabase anon key
   - `NEXT_PUBLIC_BACKEND_URL` — your Render backend URL (optional, shown in header)
4. Click **Deploy**. Vercel auto-detects Next.js.

## Run locally

```bash
cd frontend
npm install
cp .env.example .env.local   # fill in the three NEXT_PUBLIC_ values
npm run dev                  # http://localhost:3000
```

> The anon key is public by design (client-side reads). The dashboard only reads.
