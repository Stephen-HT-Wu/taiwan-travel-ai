---
name: python-style
description: Python coding conventions for taiwan-travel-ai backend. Use when editing agent.py, api.py, tdx.py, cwa.py, or main.py.
---

# Python Style (this repo)

## Principles

- Minimal diff; match existing patterns
- No over-abstraction or excessive error handling
- Comments only for non-obvious business/API quirks

## Conventions

- `load_dotenv(override=True)` in modules that read env
- Type hints: `List`, `Dict`, `Optional` (Python 3.9 compatible)
- HTTP via `httpx`; sync is fine for tool handlers
- Tool results as JSON-serializable dict/list; user-facing errors in Traditional Chinese

## File roles

| File | Purpose |
|------|---------|
| `agent.py` | Claude client, tools, streaming loop |
| `api.py` | FastAPI + SSE; session store in memory |
| `tdx.py` | TDX token + data fetchers |
| `cwa.py` | Weather fetcher |
| `main.py` | CLI entry only |

## Adding dependencies

Add to `requirements.txt`, then:
```bash
pip install -r requirements.txt
```

## Security

- Never commit `.env`
- Never log API keys
- `.gitignore`: `.env`, `venv/`, `__pycache__/`, `web/node_modules/`, `web/.next/`
