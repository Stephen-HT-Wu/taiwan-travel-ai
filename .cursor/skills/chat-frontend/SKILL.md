---
name: chat-frontend
description: Edit the Next.js chat UI in taiwan-travel-ai/web (Chat.tsx, SSE client, IME input, progress panel). Use when changing frontend UX, streaming display, tool status, or API proxy config.
---

# Chat Frontend

## Key files

```
web/
├── app/page.tsx          # renders Chat
├── components/Chat.tsx   # SSE client, messages, input
├── components/Chat.module.css
└── next.config.mjs       # proxies /api/* → 127.0.0.1:8000
```

## SSE event handling

Parse `event:` + `data:` lines from `POST /api/chat` stream:

| Event | Action |
|-------|--------|
| `status` | Update phase bar (thinking / tool / writing) |
| `tool_start` | Add activity item with provider, source, input |
| `tool_end` | Match by `id`, set summary/preview/error |
| `text_delta` | Append to streaming bubble |
| `done` | Commit assistant message + activities |

## Chinese IME (Enter to submit)

Do **not** submit on Enter when:
- `e.nativeEvent.isComposing` is true
- `composingRef.current` is true
- `enterToConfirmImeRef` is true (Enter just confirmed IME selection)

Submit button via form always works (unless `loading`).

## Styling conventions

- Dark theme via CSS variables in `globals.css`
- Progress panel during `loading`; compact activity panel on completed messages
- Keep components client-side (`"use client"`)

## After changes

```bash
cd web && npm run build   # verify types
```

Node >= 18.15 (18.17+ recommended for newer Next).
