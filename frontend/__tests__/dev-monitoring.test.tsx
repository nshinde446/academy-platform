import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import DevMonitoringPage from "@/app/(dashboard)/dev/page";
import type { DevMonitoring } from "@/app/(dashboard)/dev/_hooks/use-monitoring";

const snapshot: DevMonitoring = {
  generated_at: "2026-08-30T09:00:00Z",
  system: {
    db_size_bytes: 134217728,
    connections: 16,
    counts: { students: 30430, teachers: 28 },
  },
  devices: [
    {
      dev_id: "AMDB25083200131",
      last_seen_at: "2026-08-27T10:25:00Z",
      silent_hours: 70,
      user_count: 1181,
      face_count: 860,
    },
  ],
  attendance: { last_punch_at: "2026-08-27T09:49:00Z", punches_today: 0 },
  backup: {
    created_at: "2026-08-30T02:00:00Z",
    age_hours: 7,
    status: "ok",
    size_bytes: 80102763,
    offbox: "skipped",
  },
  queue: { pending: 62, sent: 17 },
  alerts: [
    { level: "critical", area: "device", message: "Device silent for 70h — attendance not recording." },
    { level: "warning", area: "backup", message: "Off-box copy not configured yet." },
  ],
};

vi.mock("@/store/user-store", () => ({
  useUserStore: (sel: (s: unknown) => unknown) =>
    sel({ user: { is_developer: true } }),
}));
vi.mock("@/app/(dashboard)/dev/_hooks/use-monitoring", async (orig) => ({
  ...(await orig<typeof import("@/app/(dashboard)/dev/_hooks/use-monitoring")>()),
  useDevMonitoring: () => ({ data: snapshot, isLoading: false, isError: false }),
}));

describe("DevMonitoringPage", () => {
  it("renders alerts, device status, and backup info", () => {
    render(<DevMonitoringPage />);
    expect(screen.getByText(/Active alerts \(2\)/)).toBeInTheDocument();
    expect(screen.getByText(/attendance not recording/)).toBeInTheDocument();
    expect(screen.getByText("AMDB25083200131")).toBeInTheDocument();
    expect(screen.getByText(/1181 users · 860 faces/)).toBeInTheDocument();
    // backup off-box status surfaced
    expect(screen.getByText("skipped")).toBeInTheDocument();
  });
});
