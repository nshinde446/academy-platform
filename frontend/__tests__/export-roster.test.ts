import { describe, it, expect, vi, beforeEach } from "vitest";
import apiClient from "@/services/api-client";
import { downloadCsvTemplate } from "@/lib/csv-template";
import {
  exportRosterCsv,
  fetchAllRoster,
  rosterToRows,
} from "@/app/(dashboard)/students/_lib/export-roster";
import type { StudentWithStats } from "@/app/(dashboard)/students/_schemas/student";

vi.mock("@/services/api-client", () => ({
  default: { get: vi.fn() },
}));
vi.mock("@/lib/csv-template", () => ({
  downloadCsvTemplate: vi.fn(),
}));

function row(over: Partial<StudentWithStats> = {}): StudentWithStats {
  return {
    id: "x",
    first_name: "Asha",
    last_name: "Rao",
    enrollment_number: "R-1",
    standard: "11",
    target_exam: "NEET",
    stream: "PCB",
    batch_id: "b",
    batch_name: "NEET-A",
    fees_status: "paid",
    avg_score_pct: 82.4,
    attendance_pct: 95.6,
    dpp_completion_pct: 70.2,
    batch_rank: 1,
    batch_size: 4,
    tests_taken: 3,
    ...over,
  };
}

const get = apiClient.get as ReturnType<typeof vi.fn>;

beforeEach(() => {
  get.mockReset();
  (downloadCsvTemplate as ReturnType<typeof vi.fn>).mockReset();
});

describe("export-roster", () => {
  it("pages through the roster until every row is collected", async () => {
    // total = 250 → two pages (200 + 50).
    const page1 = Array.from({ length: 200 }, (_, i) => row({ id: `a${i}` }));
    const page2 = Array.from({ length: 50 }, (_, i) => row({ id: `b${i}` }));
    get
      .mockResolvedValueOnce({ data: { items: page1, total: 250 } })
      .mockResolvedValueOnce({ data: { items: page2, total: 250 } });

    const all = await fetchAllRoster("b1", { search: "", sortBy: "name", order: "asc" });

    expect(all).toHaveLength(250);
    expect(get).toHaveBeenCalledTimes(2);
    // Second call advances the offset by one page.
    expect(get.mock.calls[1][1].params.offset).toBe(200);
  });

  it("stops on an empty page instead of looping forever", async () => {
    get.mockResolvedValue({ data: { items: [], total: 9999 } });
    const all = await fetchAllRoster("b1", { search: "" });
    expect(all).toHaveLength(0);
    expect(get).toHaveBeenCalledTimes(1);
  });

  it("maps rows to flat CSV cells with rounded percentages", () => {
    const rows = rosterToRows([row()]);
    expect(rows[0]).toEqual([
      "Asha Rao",
      "R-1",
      "11",
      "NEET",
      "PCB",
      "NEET-A",
      "1",
      "82",
      "96",
      "70",
      "paid",
      "3",
    ]);
  });

  it("blanks nullable fields", () => {
    const rows = rosterToRows([
      row({
        enrollment_number: null,
        standard: null,
        target_exam: null,
        stream: null,
        batch_name: null,
        batch_rank: null,
        fees_status: null,
      }),
    ]);
    expect(rows[0].slice(1, 7)).toEqual(["", "", "", "", "", ""]);
    expect(rows[0][10]).toBe("");
  });

  it("downloads a dated CSV and returns the row count", async () => {
    get.mockResolvedValueOnce({ data: { items: [row()], total: 1 } });
    const n = await exportRosterCsv("b1", { search: "" });
    expect(n).toBe(1);
    const dl = downloadCsvTemplate as ReturnType<typeof vi.fn>;
    expect(dl).toHaveBeenCalledTimes(1);
    expect(dl.mock.calls[0][0]).toMatch(/^students-\d{4}-\d{2}-\d{2}\.csv$/);
  });
});
