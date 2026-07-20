import { describe, it, expect } from "vitest";
import type { ErrorEvent } from "@sentry/nextjs";

import {
  REDACTED,
  isSensitiveKey,
  scrub,
  scrubEvent,
  scrubUrl,
} from "@/lib/sentry-scrub";

// Sentry is an external processor and these pages render student personal
// data. These are safety tests: a regression leaks names and phone numbers.

describe("isSensitiveKey", () => {
  it("matches case-insensitively and as a substring", () => {
    expect(isSensitiveKey("email")).toBe(true);
    expect(isSensitiveKey("Parent_Email")).toBe(true);
    expect(isSensitiveKey("STUDENT_PHONE")).toBe(true);
  });

  it("leaves ordinary keys alone", () => {
    expect(isSensitiveKey("batch_id")).toBe(false);
    expect(isSensitiveKey("lecture_status")).toBe(false);
  });
});

describe("scrub", () => {
  it("redacts personal data but keeps diagnostic fields", () => {
    const out = scrub({
      student_name: "Asha Patil",
      parent_phone: "9876543210",
      batch_id: "b-1",
    }) as Record<string, unknown>;

    expect(out.student_name).toBe(REDACTED);
    expect(out.parent_phone).toBe(REDACTED);
    expect(out.batch_id).toBe("b-1");
  });

  it("recurses into nested arrays and objects", () => {
    const out = scrub({
      rows: [{ full_name: "X", roll_no: "12", id: "s-1" }],
    }) as { rows: Record<string, unknown>[] };

    expect(out.rows[0].full_name).toBe(REDACTED);
    expect(out.rows[0].roll_no).toBe(REDACTED);
    expect(out.rows[0].id).toBe("s-1");
  });

  it("does not mutate its input", () => {
    const original = { email: "a@b.c" };
    scrub(original);
    expect(original.email).toBe("a@b.c");
  });

  it("terminates on deeply nested structures", () => {
    let deep: Record<string, unknown> = { email: "leak@example.com" };
    for (let i = 0; i < 40; i++) deep = { child: deep };
    expect(() => scrub(deep)).not.toThrow();
  });
});

describe("scrubUrl", () => {
  it("strips the query string, which carries ids and names", () => {
    expect(scrubUrl("/students?name=Asha&batch=b-1")).toBe("/students");
  });

  it("leaves a bare path untouched", () => {
    expect(scrubUrl("/lectures")).toBe("/lectures");
  });
});

describe("scrubEvent", () => {
  it("drops cookies and headers wholesale", () => {
    const event = {
      request: {
        url: "/x",
        cookies: { access_token: "secret" },
        headers: { authorization: "Bearer secret" },
      },
    } as unknown as ErrorEvent;

    const out = scrubEvent(event);
    expect(out?.request?.cookies).toBeUndefined();
    expect(out?.request?.headers).toBeUndefined();
  });

  it("strips the query string from the request url", () => {
    const event = {
      request: { url: "/students?phone=9876543210" },
    } as unknown as ErrorEvent;

    expect(scrubEvent(event)?.request?.url).toBe("/students");
  });

  it("reduces user context to a bare id", () => {
    const event = {
      user: { id: "u-1", email: "a@b.c", ip_address: "1.2.3.4" },
    } as unknown as ErrorEvent;

    const out = scrubEvent(event);
    expect(out?.user).toEqual({ id: "u-1" });
  });

  it("scrubs breadcrumb data", () => {
    const event = {
      breadcrumbs: [{ data: { student_name: "Asha", status: "ok" } }],
    } as unknown as ErrorEvent;

    const crumb = scrubEvent(event)?.breadcrumbs?.[0].data as Record<
      string,
      unknown
    >;
    expect(crumb.student_name).toBe(REDACTED);
    expect(crumb.status).toBe("ok");
  });

  it("returns null rather than throwing on a malformed event", () => {
    const hostile = {
      get request(): never {
        throw new Error("boom");
      },
    } as unknown as ErrorEvent;

    expect(scrubEvent(hostile)).toBeNull();
  });
});
