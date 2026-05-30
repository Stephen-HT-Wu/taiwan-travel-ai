const STORAGE_KEY = "taiwan-travel-ai-session-id";

function createSessionId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `session-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

export function getOrCreateSessionId(): string {
  const existing = localStorage.getItem(STORAGE_KEY);
  if (existing) return existing;

  const id = createSessionId();
  localStorage.setItem(STORAGE_KEY, id);
  return id;
}
