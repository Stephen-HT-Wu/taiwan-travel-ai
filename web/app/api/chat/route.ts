const BACKEND_URL = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

export async function POST(req: Request) {
  const body = await req.text();

  const upstream = await fetch(`${BACKEND_URL}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body,
    cache: "no-store",
  });

  if (!upstream.ok || !upstream.body) {
    return new Response(upstream.statusText, { status: upstream.status });
  }

  return new Response(upstream.body, {
    status: upstream.status,
    headers: {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}
