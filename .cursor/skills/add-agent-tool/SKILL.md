---
name: add-agent-tool
description: Add or modify Claude agent tools in taiwan-travel-ai (agent.py, tdx.py, cwa.py, osm_places.py). Use when adding data sources, tool schemas, handlers, SSE events, or LLM providers.
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
api.py          → FastAPI SSE endpoint (usually no change needed)
```

## Data source priority

1. **Places / food** → `search_places` (OSM) first
2. **Official registry** → `search_attractions` / `search_restaurants` (TDX), label as 觀光署登錄
3. **Transit / weather / routes** → dedicated tools only

## Checklist

1. **Data function** in `osm_places.py`, `tdx.py`, or `cwa.py`
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

9. **Test**
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
