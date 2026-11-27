// Talking to the simulator server (teams_sim/server.py): plain fetch helpers + one live connection per tab.
// URLs are relative, so this works when the server serves the screens (port 5100) and through the Vite proxy (npm run dev).
import { useEffect, useRef } from "react";

/** Showcase mode: the agreed design showcases (fake Max answers, scripted moments) run on mock data.
 *  Any of these URL params turns it on. Without them the screens use the real server (real mode). */
export const SHOWCASE = ["demo", "fresh", "step"].some((p) => new URLSearchParams(window.location.search).has(p));

// ---------------------------------------------------------------- shapes (as the server sends them)

export interface ApiPerson { id: string; name: string; role: string; is_bot: number }
export interface ApiChannel { id: string; team_id: string; name: string; private: number; pos: number }
export interface ApiTeam { id: string; name: string; members: string[]; channels: ApiChannel[] }
export interface ApiChat { id: string; kind: "max" | "group" | "oneToOne"; title: string | null; members: string[] }
export interface World { me: ApiPerson; people: ApiPerson[]; directory: Record<string, string>; teams: ApiTeam[]; chats: ApiChat[] }

/** A file in a channel's Files tab (newest change first). `version` = latest; `versions` = every version, oldest first. */
export interface ApiFileVersion { v: number; by: string; at: string; size: number }
export interface ApiFile { id: string; name: string; place: string; version: number; by: string; at: string; size: number; versions: ApiFileVersion[] }

export interface ApiMessage {
  id: string;
  where_kind: "channel" | "chat";
  where_id: string;
  thread_id: string | null;
  author: string;
  text: string;
  mentions: string[];
  attachments: { contentType?: string; content?: object }[];
  quote: { id: string; author: string; text: string } | null;
  created_at: string; // UTC ISO
  edited_at: string | null;
  deleted: number;
  ai_label: number; // the bot marked it "AI generated"
  feedback: number; // the bot asked for 👍/👎
}
export interface ApiThread extends ApiMessage { replies: ApiMessage[] }

export type LiveEvent =
  | { type: "message"; message: ApiMessage; stream_id?: string | null }
  | { type: "update"; message: ApiMessage }
  | { type: "typing"; kind: string; where: string; thread_id: string | null; who: string }
  | { type: "stream"; kind: string; where: string; thread_id: string | null; stream_id: string; text: string }
  | { type: "reset" }
  | { type: "connected" }; // made here: the connection is (again) open, so reload: anything sent before it opened was missed

// ---------------------------------------------------------------- fetch helpers

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, init);
  if (!r.ok) throw new Error(`${init?.method ?? "GET"} ${path}: ${r.status}`);
  return r.json() as Promise<T>;
}
const as = (me: string) => `as=${encodeURIComponent(me)}`;

export const api = {
  state: (me: string) => call<World>(`/api/state?${as(me)}`),
  threads: (me: string, channel: string) => call<ApiThread[]>(`/api/channels/${encodeURIComponent(channel)}/threads?${as(me)}`),
  chatMessages: (me: string, chat: string) => call<ApiMessage[]>(`/api/chats/${encodeURIComponent(chat)}/messages?${as(me)}`),
  files: (me: string, channel: string) => call<ApiFile[]>(`/api/channels/${encodeURIComponent(channel)}/files?${as(me)}`),
  /** The file itself (opens in the browser for PDF/images, downloads for Office files). No `v` = latest version. */
  fileUrl: (me: string, id: string, v?: number) => `/api/files/${encodeURIComponent(id)}?${as(me)}${v ? `&v=${v}` : ""}`,
  post: (body: { as: string; kind: "channel" | "chat"; where: string; text: string; thread_id?: string; quote_id?: string }) =>
    call<ApiMessage>("/api/messages", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }),
  reset: () => call<{ ok: boolean }>("/api/reset", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" }),
};

// ---------------------------------------------------------------- live updates: one WebSocket per tab

const listeners = new Set<(e: LiveEvent) => void>();
let socket: WebSocket | null = null;
let liveAs = "";
let retryTimer = 0;
let retries = 0;

const emit = (e: LiveEvent) => listeners.forEach((fn) => fn(e));

/** Open (or switch) the live connection for this person. Reconnects by itself after a drop. */
export function startLive(me: string) {
  if (liveAs === me && socket) return;
  stopLive();
  liveAs = me;
  const open = () => {
    const ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/api/live?${as(me)}`);
    socket = ws;
    ws.onopen = () => { retries = 0; emit({ type: "connected" }); }; // also the first time: closes the gap between loading and connecting
    ws.onmessage = (m) => { try { emit(JSON.parse(m.data)); } catch { /* not ours */ } };
    ws.onclose = () => {
      if (socket !== ws) return; // replaced on purpose
      socket = null;
      retryTimer = window.setTimeout(open, Math.min(10_000, 500 * 2 ** retries++));
    };
  };
  open();
}

export function stopLive() {
  window.clearTimeout(retryTimer);
  const ws = socket;
  socket = null;
  liveAs = "";
  ws?.close();
}

/** Listen to live events while the component is shown (and `enabled`). The latest handler is always used. */
export function useLive(handler: (e: LiveEvent) => void, enabled = true) {
  const ref = useRef(handler);
  ref.current = handler;
  useEffect(() => {
    if (!enabled) return;
    const fn = (e: LiveEvent) => ref.current(e);
    listeners.add(fn);
    return () => { listeners.delete(fn); };
  }, [enabled]);
}

// ---------------------------------------------------------------- times, shown in JST like the rest of the screens

const JST = new Intl.DateTimeFormat("en-GB", {
  timeZone: "Asia/Tokyo", weekday: "short", day: "numeric", month: "short", year: "numeric",
  hour: "2-digit", minute: "2-digit", hourCycle: "h23",
});
function parts(d: Date) {
  const p = Object.fromEntries(JST.formatToParts(d).map((x) => [x.type, x.value]));
  return { date: `${p.weekday} ${p.day} ${p.month}`, key: `${p.year}-${p.month}-${p.day}`, time: `${p.hour}:${p.minute}` };
}

/** "14:32" today, "Thu 20 Nov 14:32" on other days (channel posts). */
export function postTime(iso: string): string {
  const t = parts(new Date(iso));
  return t.key === parts(new Date()).key ? t.time : `${t.date} ${t.time}`;
}

/** Files tab: like posts, but "Today 14:32" (a bare time looks odd in a list of dates). */
export function fileTime(iso: string): string {
  const t = postTime(iso);
  return t.length <= 5 ? `Today ${t}` : t;
}

/** "84 KB", "2.1 MB" (at least 1 KB, like Teams). */
export function fileSize(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  return `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

/** Chat bubbles: the time ("14:32") and the day divider ("Today", "Yesterday", "Thu 20 Nov"). */
export function chatTime(iso: string): { time: string; day: string } {
  const t = parts(new Date(iso));
  const today = parts(new Date()).key;
  const yesterday = parts(new Date(Date.now() - 86_400_000)).key;
  return { time: t.time, day: t.key === today ? "Today" : t.key === yesterday ? "Yesterday" : t.date };
}
