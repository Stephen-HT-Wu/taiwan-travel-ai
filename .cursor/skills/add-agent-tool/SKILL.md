---
name: add-agent-tool
description: Add or modify Claude agent tools in taiwan-travel-ai (agent.py, tdx.py, cwa.py). Use when adding TDX/CWA data sources, tool schemas, handlers, SSE events, or extending the travel assistant capabilities.
---

# Add Agent Tool

## Architecture

```
agent.py   → tool schema, TOOL_HANDLERS, TOOL_META, stream_agent()
tdx.py     → TDX OAuth + tourism/transit APIs
cwa.py     → Central Weather Administration API
api.py     → FastAPI SSE endpoint (usually no change needed)
```

## Checklist

1. **Data function** in `tdx.py` or `cwa.py`
   - Reuse `_tdx_get()` for TDX; use `load_dotenv(override=True)`
   - Return `list[dict]` or `dict`; put errors in `{"error": "..."}` not exceptions when possible
   - Truncate long text fields (~200 chars)

2. **Tool schema** in `agent.py` `tools` list
   - Clear `description` so Claude knows when to call it
   - Use English city names for TDX (e.g. `Tainan`, `Taipei`, `HualienCounty`)

3. **Handler** in `TOOL_HANDLERS`

4. **Metadata** in `TOOL_META` (label, source, provider) for UI data-source panel

5. **Summarize** in `summarize_tool_result()` if preview needs custom logic

6. **Test**
   ```bash
   source venv/bin/activate
   python -c "from agent import execute_tool; print(execute_tool('your_tool', {...}))"
   ```

## SSE events (auto via stream_agent)

- `status` → thinking / tool / writing phases
- `tool_start` → includes id, label, source, provider, input
- `tool_end` → includes ok, summary, preview, count
- `text_delta` / `done`

## TDX pitfalls

- Verify `$select` fields exist (BusRoute has `SubRoutes`, not top-level `SubRouteName`)
- City enum varies by API; test with `httpx` before committing
- Token cache in `get_tdx_token()`; avoid redundant auth calls

## Do not

- Commit `.env` or API keys
- Break CLI (`main.py` uses same `run_agent`)
