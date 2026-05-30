---
name: python-style
description: Python coding conventions for taiwan-travel-ai backend. Use when editing agent.py, api.py, tdx.py, cwa.py, routing.py, transit.py, osm_places.py, or main.py.
---

# Python Style (this repo)

## Principles

- Minimal diff; match existing patterns
- No over-abstraction or excessive error handling
- Comments only for non-obvious business/API quirks

## Engineering principles (this repo)

- **KISS first:** Prefer a small, readable change over clever abstractions. Refactor only when duplication or file size clearly hurts maintainability (e.g. same TDX parse logic in two modules).
- **Single responsibility:** Data fetch/parse lives in `tdx.py`, `cwa.py`, `osm_places.py`, `routing.py`, `transit.py` — not in `agent.py`. Orchestration, prompts, and SSE stay in `agent.py` / `api.py`.
- **DRY with judgment:** Extract shared helpers when the same logic appears twice; do not introduce base classes or plugin registries for a one-off tool.
- **Naming:** Use self-documenting names for functions and dict keys returned to the LLM (`duration_minutes`, `feasible`, not `d` / `ok2`).
- **Errors:** Return JSON-serializable `{"error": "繁中說明"}` from data modules. Let `execute_tool` in `agent.py` catch unexpected exceptions — avoid wrapping every `httpx` call in its own try-except unless there is a specific fallback path.
- **Edge cases:** Validate inputs at tool boundaries (empty lists, missing lat/lng, invalid city). Empty success → `[]` or structured empty result, not uncaught `KeyError`.

## Refactor triggers

| Signal | Action |
|--------|--------|
| Duplicate TDX/OSM fetch or parse | Move to `tdx.py` or `transit.py` |
| Magic city / rail strings | Reuse `osm_places.CITY_ZH`, `transit.CITY_RAIL_SYSTEMS` |
| Same tool wiring copy-pasted 4+ times in `agent.py` | Small local helper only — not a generic plugin framework |
| Long function with mixed fetch + format | Split fetch (data module) from shape (return dict) |

## Conventions

- `load_dotenv(override=True)` in modules that read env
- Type hints: `List`, `Dict`, `Optional` (Python 3.9 compatible)
- HTTP via `httpx`; sync is fine for tool handlers
- Tool results as JSON-serializable dict/list; user-facing errors in Traditional Chinese

## File roles

| File | Purpose |
|------|---------|
| `agent.py` | Tools, prompts, streaming loop, tool result compaction |
| `api.py` | FastAPI + SSE; session store in memory |
| `tdx.py` | TDX token + tourism/transit schedule fetchers |
| `cwa.py` | Weather fetcher |
| `osm_places.py` | OSM POI search |
| `routing.py` | Nominatim + OSRM route/legs |
| `transit.py` | TDX bus/metro stops + segment estimates |
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
