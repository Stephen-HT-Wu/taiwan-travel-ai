---
name: run-and-debug
description: Run, test, and debug the taiwan-travel-ai dev stack (Python FastAPI, Next.js, env vars). Use when starting servers, fixing API/proxy errors, or troubleshooting CWA/TDX/Anthropic integration.
---

# Run and Debug

## Start dev stack

Terminal 1 — backend:
```bash
cd taiwan-travel-ai
source venv/bin/activate
pip install -r requirements.txt
uvicorn api:app --reload --port 8000
```

Terminal 2 — frontend:
```bash
cd web
npm install
npm run dev
```

Open http://localhost:3000

## Required env (.env, never commit)

```
TDX_CLIENT_ID / TDX_CLIENT_SECRET
ANTHROPIC_API_KEY
CWA_API_KEY   # weather only; register at opendata.cwa.gov.tw
```

**After editing `.env`, restart uvicorn** — reload does not re-read env reliably.

## Common failures

| Symptom | Fix |
|---------|-----|
| `API 請求失敗` / proxy 500 | Next proxy must use `127.0.0.1:8000` not `localhost` (IPv6 issue) |
| `未設定 CWA_API_KEY` | Add key to `.env`, restart backend |
| TDX 400 on `$select` | Field name wrong; test API without `$select` first |
| TDX 429 | Rate limit; wait or reduce calls |
| Next `Cannot find module './xxx.js'` | `rm -rf web/.next && npm run dev` |
| `loading` stuck / can't send | Hard refresh; check backend health |

## Quick checks

```bash
curl http://127.0.0.1:8000/api/health
curl -N -X POST http://127.0.0.1:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"台南景點","session_id":"test"}'
```

## CLI mode (no web)

```bash
python main.py
```
