import { useCallback, useEffect, useRef, useState } from "react";
import { MODULE_BY_ID } from "./modules";
import type { ModuleId } from "./modules";

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  /** ISO timestamp, shown as a small time under each bubble */
  createdAt: string;
};

/* =====================================================================
   BACKEND ADAPTER
   These four functions are the ONLY place the UI talks to FastAPI.
   If your endpoints differ, change them here and nowhere else.
   Every call takes a moduleId, so there is no global conversation.

   DESIGN NOTE — no hardcoded hostnames:
   The Next.js next.config.ts rewrites /api/*, /chat/*, /health, etc.
   to the FastAPI backend.  The browser therefore always POSTs to the
   same origin that served the page (whether that is localhost:3000 or
   192.168.x.x:3000), so the app works identically on desktop and on
   any mobile device that shares the same Wi-Fi network.
   ===================================================================== */

/**
 * Invisible backend API URL resolution:
 * 1. NEXT_PUBLIC_API_URL environment variable if provided at build time (e.g., via GitHub Actions)
 * 2. Query parameter override (?api=https://... or ?backend=...) saved silently to localStorage
 * 3. Stored localStorage URL ("jarvis_api_url")
 * 4. Dynamic window.location.hostname fallback when running locally on Wi-Fi (or 127.0.0.1:8000)
 */
export function getApiBase(): string {
  const envUrl =
    process.env.NEXT_PUBLIC_API_URL ||
    process.env.NEXT_PUBLIC_JARVIS_API_URL ||
    process.env.NEXT_PUBLIC_JARVIS_API;

  if (typeof window === "undefined") {
    return envUrl ? envUrl.trim().replace(/\/+$/, "") : "http://127.0.0.1:8000";
  }

  // Check URL query parameter: ?api=https://... or ?backend=...
  try {
    const params = new URLSearchParams(window.location.search);
    const queryApi = params.get("api") || params.get("backend");
    if (queryApi && queryApi.trim()) {
      const cleanUrl = queryApi.trim().replace(/\/+$/, "");
      localStorage.setItem("jarvis_api_url", cleanUrl);
      return cleanUrl;
    }
  } catch {
    // ignore query parameter access errors
  }

  // Check silently stored localStorage URL
  try {
    const stored = localStorage.getItem("jarvis_api_url");
    if (stored && stored.trim()) {
      return stored.trim().replace(/\/+$/, "");
    }
  } catch {
    // ignore localStorage access errors
  }

  // Build-time env URL fallback
  if (envUrl && envUrl.trim()) {
    return envUrl.trim().replace(/\/+$/, "");
  }

  // Dynamic hostname resolution for local development & Wi-Fi LAN
  const host = window.location.hostname;
  const isLocal =
    host === "localhost" ||
    host === "127.0.0.1" ||
    /^192\.168\.\d+\.\d+$/.test(host) ||
    /^10\.\d+\.\d+\.\d+$/.test(host) ||
    /^172\.(1[6-9]|2\d|3[01])\.\d+\.\d+$/.test(host);

  if (isLocal) {
    return `${window.location.protocol}//${host}:8000`;
  }

  // Hosted on GitHub Pages without configured tunnel defaults to local backend
  return "http://127.0.0.1:8000";
}

export function getWsBase(): string {
  const api = getApiBase();
  return api.replace(/^http:/, "ws:").replace(/^https:/, "wss:");
}

export function getBackendUrls() {
  if (typeof window !== "undefined") {
    const params = new URLSearchParams(window.location.search);
    const apiParam = params.get("api");
    if (apiParam) {
      const cleanUrl = apiParam.replace(/\/$/, "");
      localStorage.setItem("jarvis_api_url", cleanUrl);
    }
    const saved = localStorage.getItem("jarvis_api_url");
    if (saved) {
      return {
        httpUrl: saved,
        wsUrl: saved.replace(/^https:/, "wss:").replace(/^http:/, "ws:"),
      };
    }
    const host = window.location.hostname;
    return {
      httpUrl: `http://${host}:8000`,
      wsUrl: `ws://${host}:8000`,
    };
  }
  return { httpUrl: "http://localhost:8000", wsUrl: "ws://localhost:8000" };
}

const THREAD = "main";

const threadPath = (moduleId: ModuleId) =>
  `/api/modules/${MODULE_BY_ID[moduleId].apiId}/threads/${THREAD}`;

export async function fetchHistory(moduleId: ModuleId): Promise<ChatMessage[]> {
  const data = await http<RawMessage[] | { messages?: RawMessage[] }>(`${threadPath(moduleId)}/messages`);
  const list = Array.isArray(data) ? data : data.messages ?? [];
  return list.map((raw) => normalise(raw, "assistant"));
}

/**
 * sendTurn — Real-time SSE streaming with automatic POST fallback.
 */
export async function sendTurn(
  moduleId: ModuleId,
  message: string,
  onDelta?: (token: string) => void
): Promise<ChatMessage> {
  const streamPath = `${threadPath(moduleId)}/stream?message=${encodeURIComponent(message)}`;
  const directUrl = `${getApiBase()}${streamPath}`;

  return new Promise<ChatMessage>((resolve, reject) => {
    let resolved = false;
    let accumulated = "";
    let finalId = `m-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    let finalCreatedAt = new Date().toISOString();

    let es: EventSource | null = null;
    try {
      es = new EventSource(directUrl);
    } catch {
      // EventSource instantiation failed, fallback immediately
      fallbackPost();
      return;
    }

    function fallbackPost() {
      if (resolved) return;
      resolved = true;
      if (es) {
        es.close();
        es = null;
      }
      http<RawMessage>(`${threadPath(moduleId)}/chat`, {
        method: "POST",
        body: JSON.stringify({ message }),
      })
        .then((data) => resolve(normalise({ ...data, role: "assistant" }, "assistant")))
        .catch(reject);
    }

    es.onmessage = (event) => {
      if (event.data === "[DONE]") {
        if (es) es.close();
        resolved = true;
        resolve({
          id: finalId,
          role: "assistant",
          content: accumulated,
          createdAt: finalCreatedAt,
        });
        return;
      }
      try {
        const chunk = JSON.parse(event.data) as {
          delta?: string;
          done?: boolean;
          id?: number;
          created_at?: string;
          error?: string;
        };
        if (chunk.error) {
          if (es) es.close();
          resolved = true;
          reject(new Error(chunk.error));
          return;
        }
        if (chunk.delta) {
          accumulated += chunk.delta;
          onDelta?.(chunk.delta);
        }
        if (chunk.done) {
          if (chunk.id) finalId = String(chunk.id);
          if (chunk.created_at) finalCreatedAt = toIso(chunk.created_at);
        }
      } catch {
        // malformed chunk
      }
    };

    es.onerror = () => {
      // If error occurs before any tokens received, fall back to POST
      if (!accumulated) {
        fallbackPost();
      } else {
        // Already received partial tokens; finish what we have
        if (es) es.close();
        resolved = true;
        resolve({
          id: finalId,
          role: "assistant",
          content: accumulated,
          createdAt: finalCreatedAt,
        });
      }
    };
  });
}

export async function resetThread(moduleId: ModuleId): Promise<void> {
  await http(threadPath(moduleId), { method: "DELETE" });
}

export async function checkHealth(): Promise<void> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 3500);
  try {
    const directUrl = `${getApiBase()}/health`;
    try {
      const response = await fetch(directUrl, { signal: controller.signal });
      if (response.ok) return;
    } catch {
      // Direct call failed, fallback to Next.js proxy rewrite
    }
    const proxyResponse = await fetch("/health", { signal: controller.signal });
    if (proxyResponse.ok) return;
    throw new Error("Health check failed");
  } finally {
    clearTimeout(timer);
  }
}

/* ---------- plumbing (no need to touch) ---------- */
type RawMessage = {
  id?: string | number;
  role?: string;
  content?: string;
  reply?: string;
  text?: string;
  created_at?: string;
  createdAt?: string;
  timestamp?: string;
};

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const directUrl = `${getApiBase()}${path}`;
  let response: Response;
  try {
    response = await fetch(directUrl, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
    });
    if (!response.ok) {
      throw new Error(`Direct request returned status ${response.status}`);
    }
  } catch {
    // If direct connection fails, fall back to Next.js proxy rewrite
    response = await fetch(path, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
    });
  }
  const data: unknown = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = (data as { detail?: unknown }).detail;
    throw new Error(typeof detail === "string" ? detail : `Request failed (${response.status})`);
  }
  return data as T;
}

// SQLite writes "2026-11-22 12:34:56" in UTC with no zone, which browsers read as local time.
function toIso(value: string | undefined): string {
  if (!value) return new Date().toISOString();
  return /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}/.test(value) ? `${value.replace(" ", "T")}Z` : value;
}

function normalise(raw: RawMessage, fallbackRole: ChatMessage["role"]): ChatMessage {
  return {
    id: String(raw.id ?? `m-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`),
    role: raw.role === "user" ? "user" : raw.role === "assistant" ? "assistant" : fallbackRole,
    content: raw.content ?? raw.reply ?? raw.text ?? "",
    createdAt: toIso(raw.created_at ?? raw.createdAt ?? raw.timestamp),
  };
}

/* =====================================================================
   useModuleChat(moduleId)
   One call per module page. All state lives inside that call, so a draft,
   a spinner, an error or a reset in one module cannot reach another one.

   Streaming: each token from the SSE stream is appended to the last
   "assistant" bubble in real time, so the user sees the reply being typed.
   ===================================================================== */
export function useModuleChat(moduleId: ModuleId, active: boolean) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const started = useRef(false);

  // Load this module's saved history once, the first time its tab is opened.
  useEffect(() => {
    if (!active || started.current) return;
    started.current = true;
    fetchHistory(moduleId)
      .then((history) => setMessages((previous) => (previous.length === 0 ? history : previous)))
      .catch(() => {
        /* backend offline: start with an empty chat */
      });
  }, [active, moduleId]);

  const send = useCallback(
    async (text?: string) => {
      const message = (text ?? draft).trim();
      if (!message || loading) return;

      setError("");
      setNotice("");

      // Immediately show the user bubble.
      setMessages((previous) => [
        ...previous,
        { id: `local-${Date.now()}`, role: "user", content: message, createdAt: new Date().toISOString() },
      ]);
      setDraft("");
      setLoading(true);

      // Insert an empty assistant bubble that we'll fill token-by-token.
      const streamId = `stream-${Date.now()}`;
      setMessages((previous) => [
        ...previous,
        { id: streamId, role: "assistant", content: "", createdAt: new Date().toISOString() },
      ]);

      try {
        const reply = await sendTurn(moduleId, message, (token) => {
          // Append each streamed token to the placeholder bubble.
          setMessages((previous) =>
            previous.map((msg) =>
              msg.id === streamId ? { ...msg, content: msg.content + token } : msg
            )
          );
        });

        // Replace the stream placeholder with the finalised message (correct id/timestamp).
        setMessages((previous) =>
          previous.map((msg) => (msg.id === streamId ? reply : msg))
        );
      } catch (caught) {
        // Remove the empty placeholder on error.
        setMessages((previous) => previous.filter((msg) => msg.id !== streamId));
        setError(caught instanceof Error ? caught.message : "Could not reach the local JARVIS service.");
      } finally {
        setLoading(false);
      }
    },
    [draft, loading, moduleId]
  );

  const reset = useCallback(async () => {
    if (loading) return;
    try {
      await resetThread(moduleId);
      setMessages([]);
      setError("");
      setNotice("Conversation cleared.");
    } catch {
      setNotice("Couldn't clear this conversation on the backend. Your visible chat was kept.");
    }
  }, [loading, moduleId]);

  return { messages, draft, setDraft, loading, error, notice, send, reset };
}
