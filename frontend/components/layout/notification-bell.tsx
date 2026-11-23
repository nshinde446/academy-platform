"use client";

import { useEffect, useRef, useState } from "react";
import { Bell } from "lucide-react";
import apiClient from "@/services/api-client";

interface Notification {
  id: string;
  record_type: string | null;
  record_id: string | null;
  message: string;
  is_read: boolean;
  created_at: string;
}

const POLL_MS = 60_000;

// In-app notification bell (SRD AP07). Polls the unread count and, on open,
// shows the recent list with mark-as-read. Used in both the teacher portal and
// the admin dashboard sidebars — it reads /me/notifications, which is the
// current user regardless of which shell they are in.
export function NotificationBell() {
  const [count, setCount] = useState(0);
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<Notification[]>([]);
  const wrapRef = useRef<HTMLDivElement>(null);

  // Poll the unread count.
  useEffect(() => {
    let on = true;
    const tick = async () => {
      try {
        const r = await apiClient.get<{ count: number }>("/api/v1/me/notifications/unread-count");
        if (on) setCount(r.data.count);
      } catch {
        /* silent — the bell is non-critical */
      }
    };
    void tick();
    const id = setInterval(tick, POLL_MS);
    return () => {
      on = false;
      clearInterval(id);
    };
  }, []);

  // Load the list when opened.
  useEffect(() => {
    if (!open) return;
    let on = true;
    (async () => {
      try {
        const r = await apiClient.get<Notification[]>("/api/v1/me/notifications");
        if (on) setItems(r.data);
      } catch {
        /* silent */
      }
    })();
    return () => { on = false; };
  }, [open]);

  // Close on outside click.
  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  async function markAllRead() {
    try {
      await apiClient.post("/api/v1/me/notifications/read-all");
      setItems((xs) => xs.map((n) => ({ ...n, is_read: true })));
      setCount(0);
    } catch {
      /* silent */
    }
  }

  async function markRead(n: Notification) {
    if (n.is_read) return;
    try {
      await apiClient.post(`/api/v1/me/notifications/${n.id}/read`);
      setItems((xs) => xs.map((x) => (x.id === n.id ? { ...x, is_read: true } : x)));
      setCount((c) => Math.max(0, c - 1));
    } catch {
      /* silent */
    }
  }

  return (
    <div ref={wrapRef} className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        aria-label={`Notifications${count ? ` (${count} unread)` : ""}`}
        className="relative grid h-8 w-8 place-items-center rounded-md border border-border text-foreground transition-colors hover:bg-muted"
      >
        <Bell className="h-4 w-4" aria-hidden />
        {count > 0 && (
          <span className="absolute -right-1 -top-1 grid h-4 min-w-4 place-items-center rounded-full bg-red-500 px-1 text-[9px] font-semibold text-white">
            {count > 9 ? "9+" : count}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute bottom-full right-0 z-50 mb-2 max-h-80 w-72 overflow-y-auto rounded-lg border bg-popover shadow-lg">
          <div className="flex items-center justify-between border-b px-3 py-2">
            <span className="text-xs font-semibold">Notifications</span>
            {items.some((n) => !n.is_read) && (
              <button className="text-[11px] text-primary underline" onClick={markAllRead}>
                Mark all read
              </button>
            )}
          </div>
          {items.length === 0 ? (
            <p className="px-3 py-4 text-xs text-muted-foreground">No notifications yet.</p>
          ) : (
            <ul className="flex flex-col">
              {items.map((n) => (
                <li key={n.id}>
                  <button
                    onClick={() => markRead(n)}
                    className={`flex w-full flex-col items-start gap-0.5 border-b px-3 py-2 text-left text-xs transition-colors hover:bg-muted ${
                      n.is_read ? "opacity-60" : "font-medium"
                    }`}
                  >
                    <span>{n.message}</span>
                    <span className="text-[10px] text-muted-foreground">
                      {new Date(n.created_at).toLocaleString()}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
