import type { ErrorEvent } from "@sentry/nextjs";

/**
 * PII scrubbing for Sentry events.
 *
 * This app renders student names, phone numbers, email addresses and parent
 * contact details on most pages, and Sentry is an external processor. Nothing
 * of the sort may leave the browser: URLs are stripped of query strings,
 * known-sensitive keys are redacted, and breadcrumb/request payloads are
 * scrubbed before send.
 *
 * Mirrors `backend/app/core/observability/sentry.py` — keep the two key lists
 * in step when either changes.
 */

/** Case-insensitive substrings; a matching key has its value redacted. */
const SENSITIVE_KEYS = [
  "password",
  "token",
  "secret",
  "authorization",
  "cookie",
  "api_key",
  "apikey",
  "dsn",
  // Personal data
  "email",
  "phone",
  "mobile",
  "contact",
  "address",
  "dob",
  "date_of_birth",
  "guardian",
  "parent",
  "first_name",
  "last_name",
  "full_name",
  "student_name",
  "teacher_name",
  "aadhaar",
  "roll_no",
] as const;

export const REDACTED = "[redacted]";

const MAX_DEPTH = 12;

export function isSensitiveKey(key: string): boolean {
  const lowered = key.toLowerCase();
  return SENSITIVE_KEYS.some((marker) => lowered.includes(marker));
}

/** Recursively redact sensitive values. Returns a new structure. */
export function scrub(value: unknown, depth = 0): unknown {
  if (depth > MAX_DEPTH) return REDACTED;

  if (Array.isArray(value)) {
    return value.map((v) => scrub(v, depth + 1));
  }

  if (value !== null && typeof value === "object") {
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
      out[k] = isSensitiveKey(k) ? REDACTED : scrub(v, depth + 1);
    }
    return out;
  }

  return value;
}

/**
 * Strip the query string from a URL.
 *
 * Search params here routinely carry student ids and names (roster filters,
 * `?redirect=` targets), and the path alone is enough to locate a bug.
 */
export function scrubUrl(url: string | undefined): string | undefined {
  if (!url) return url;
  const cut = url.indexOf("?");
  return cut === -1 ? url : url.slice(0, cut);
}

/**
 * `beforeSend` hook. Defensive throughout — error reporting must never be the
 * thing that breaks the page, so a failure here drops the event rather than
 * propagating.
 */
export function scrubEvent(event: ErrorEvent): ErrorEvent | null {
  try {
    if (event.request) {
      event.request.url = scrubUrl(event.request.url);
      // Always dropped wholesale: these carry session material and never
      // contain anything needed to diagnose a crash.
      delete event.request.cookies;
      delete event.request.headers;
      if (event.request.data) {
        event.request.data = scrub(event.request.data);
      }
      delete event.request.query_string;
    }

    if (event.extra) {
      event.extra = scrub(event.extra) as typeof event.extra;
    }

    // Sentry's default user context is an IP address plus whatever id it can
    // find. Keep only a non-identifying id if one was set deliberately.
    if (event.user) {
      event.user = event.user.id ? { id: String(event.user.id) } : {};
    }

    if (event.breadcrumbs) {
      event.breadcrumbs = event.breadcrumbs.map((crumb) => ({
        ...crumb,
        data: crumb.data
          ? (scrub(crumb.data) as typeof crumb.data)
          : crumb.data,
      }));
    }

    return event;
  } catch {
    return null;
  }
}
