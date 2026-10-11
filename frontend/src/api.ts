// Single API/auth boundary. The access token lives in this module's closure
// only: never localStorage, sessionStorage, cookies, or the URL. A page reload
// is a new session because the backend has no refresh endpoint yet.
let accessToken = "";
const listeners = new Set<() => void>();

export const setToken = (token: string) => {
  accessToken = token;
  listeners.forEach((fn) => fn());
};
export const clearToken = () => setToken("");
export const hasToken = () => Boolean(accessToken);
export const onSessionLost = (fn: () => void) => {
  listeners.add(fn);
  return () => {
    listeners.delete(fn);
  };
};

export class ApiError extends Error {
  constructor(message: string, readonly status: number, readonly code = "") {
    super(message);
  }
}

const detailText = (detail: unknown, status: number): [string, string] => {
  if (typeof detail === "string") return [detail, ""];
  if (detail && typeof detail === "object") {
    const d = detail as { message?: string; code?: string };
    return [d.message || `Request failed (${status})`, d.code || ""];
  }
  return [`Request failed (${status})`, ""];
};

export const api = async <T,>(path: string, options: RequestInit = {}): Promise<T> => {
  const headers = new Headers(options.headers);
  if (!(options.body instanceof FormData)) headers.set("Content-Type", "application/json");
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);

  const res = await fetch(`/api${path}`, { ...options, headers });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    // 401 means the session is gone. Drop the token and let the shell show login.
    if (res.status === 401) clearToken();
    const [message, code] = detailText((data as { detail?: unknown }).detail, res.status);
    throw new ApiError(message, res.status, code);
  }
  return data as T;
};

export const errorText = (e: unknown, fallback: string) => (e instanceof Error ? e.message : fallback);

export type User = { id: string; email: string; role: "learner" | "admin"; status: string };
// Learner payloads intentionally carry no answer_sql/seed_sql/expected_output.
export type Question = { id: string; question_text?: string; difficulty?: string; topic?: string; status?: string; review_notes?: string };
export type Stats = { users?: number; active_users?: number; questions?: number; approved_questions?: number; pending_questions?: number; documents?: number; jobs?: number };
export type Weekly = { challenge: { title?: string; number?: number; status?: string }; progress: { done: number; total: number; percent: number }; questions: Question[] };
export type Job = { id: string; status?: string; durable?: boolean; executor?: string; error?: string; error_code?: string; created_at?: string; specs?: string[]; persisted_question_ids?: string[]; requested_by?: string; result?: unknown };
export type Doc = { id: string; filename?: string; size?: number; checksum?: string; status?: string; truncated?: boolean; created_at?: string; preview?: string };
export type LlmSettings = { provider: string; model: string; base_url: string; token_configured: boolean; token_source: string; token_hint: string; supported_providers: string[]; updated_at?: string };
export type AuditLog = { id: string; actor_id: string; action: string; resource_type: string; resource_id: string; summary: string; created_at: string };
