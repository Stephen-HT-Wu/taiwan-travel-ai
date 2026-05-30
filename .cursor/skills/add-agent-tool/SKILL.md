---
name: add-agent-tool
description: Add or modify agent tools in taiwan-travel-ai (agent.py, tdx.py, cwa.py, osm_places.py, routing.py, transit.py). Use when adding data sources, tool schemas, handlers, SSE events, or LLM providers.
---

# Add Agent Tool

## Architecture

```
agent.py        → tool schema, TOOL_HANDLERS, TOOL_META, stream_agent()
providers/      → LLM backend (anthropic | gemini)
osm_places.py   → OpenStreetMap Overpass POI (primary places)
tdx.py          → TDX OAuth + tourism/transit APIs (official supplement)
cwa.py          → Central Weather Administration API
routing.py      → Nominatim geocoding + OSRM routing
transit.py      → TDX bus/metro stops + simplified segment times
api.py          → FastAPI SSE endpoint (usually no change needed)
```

**Separation of concerns:** Data modules must not import `agent`. Prompt and “when to call which tool” rules go in `SYSTEM_PROMPT`. Adding a tool still requires wiring in `agent.py` (schema, handler map, meta, compact, often prompt) — follow the checklist below; do not build a plugin framework unless explicitly requested.

## Data source priority

1. **Places / food** → `search_places` (OSM) first
2. **Official registry** → `search_attractions` / `search_restaurants` (TDX), label as 觀光署登錄
3. **Transit / weather / routes** → dedicated tools only

## Resilience & graceful degradation

- External APIs (TDX, OSM, OSRM) can timeout or return empty data. Data functions should return `{"error": "..."}` or `[]` — never raise to the user-facing SSE path uncaught.
- `api.py` maps unexpected stream failures to a generic 繁中 message; tool handlers should fail softly with structured errors the LLM can cite honestly (“查無結果”, “查詢逾時”).
- List tools with zero rows: use `EMPTY_TOOL_NOTES` + compact payload `note` so the model does not invent POIs or times.
- Cache tokens/stops in module-level dicts (see `tdx._station_ids_cache`, `transit._bus_stops_cache`) — clear caches in tests via `conftest.py`.
- Do not double-wrap: `execute_tool` already catches handler exceptions; prefer clear errors inside data modules over nested try-except everywhere.

## Checklist

1. **Data function** in `osm_places.py`, `tdx.py`, `transit.py`, or `cwa.py`
   - Reuse existing HTTP helpers; set `User-Agent` for OSM
   - Return `list[dict]` or `dict`; errors as `{"error": "..."}`

2. **Tool schema** in `agent.py` `tools` list
   - Clear `description` including when to call vs other tools
   - Default `limit`: 20 for list tools

3. **Handler** in `TOOL_HANDLERS`

4. **Metadata** in `TOOL_META` (label, source, provider) for UI panel

5. **Map pins** — add to `MAP_TOOL_NAMES` + `extract_map_places` if lat/lng available

6. **Compact payload** — update `compact_tool_result_for_model` (max `COMPACT_LIST_LIMIT`)

7. **Empty results** — add note in `EMPTY_TOOL_NOTES` if list tool

8. **Prompt** — update `SYSTEM_PROMPT` if tool changes data-source rules

9. **Summarize** — update `summarize_tool_result` if return shape is non-list dict

10. **Test**
   ```bash
   source venv/bin/activate
   pytest tests/test_*_integration.py -q
   ```

## LLM providers

- Set `LLM_PROVIDER=anthropic|gemini` in `.env`
- New provider: implement `stream_turn` + `create_turn` in `providers/`, register in `get_llm_provider()`
- Do not change SSE event shape consumed by `web/components/Chat.tsx`

## Do not

- Commit `.env` or API keys
- Add paid APIs (Google Places) without explicit request
- Break CLI (`main.py` uses same `run_agent`)
- Change `stream_agent` event names/shapes without updating `web/components/Chat.tsx` and tests
- Add abstractions “for SOLID” that are used by only one tool
