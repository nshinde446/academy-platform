"use client";

import type { ImportPreview } from "../_schemas/student";

// T13 — a compact "what this import will do" matrix (design §7.1), aggregated
// from the existing preview so the admin sees the structural impact (new
// courses / batches / academic years) and the gates (blocked, duplicates)
// before committing.

interface Row {
  action: string;
  count: number;
  gate?: "BLOCK" | "WARN";
}

function buildRows(p: ImportPreview): Row[] {
  const newBatches = p.batches.filter((b) => !b.exists && b.creatable);
  const existing = p.batches.filter((b) => b.exists);
  const newCourses = new Set(
    newBatches.map((b) => b.suggested_course_code).filter(Boolean),
  );
  const invalidSkipped =
    p.rows_missing_name + p.rows_invalid_enrolment + p.rows_invalid_consistency;

  const rows: Row[] = [
    { action: "New courses", count: newCourses.size },
    { action: "New batches", count: newBatches.length },
    { action: "Existing batches matched", count: existing.length },
    { action: "New academic years", count: p.new_academic_years.length },
    {
      action: "Batches that can't be created",
      count: p.blocked_batches,
      gate: p.blocked_batches > 0 ? "BLOCK" : undefined,
    },
    { action: "Duplicates (skipped)", count: p.duplicate_rows },
    {
      action: "Possible duplicates (imported, flagged)",
      count: p.rows_possible_duplicate ?? 0,
      gate: (p.rows_possible_duplicate ?? 0) > 0 ? "WARN" : undefined,
    },
    {
      action: "Invalid rows (skipped)",
      count: invalidSkipped,
      gate: invalidSkipped > 0 ? "WARN" : undefined,
    },
  ];
  // Only show rows with something to report (keeps the matrix tight).
  return rows.filter((r) => r.count > 0);
}

export function ImportConfirmMatrix({ preview }: { preview: ImportPreview }) {
  const rows = buildRows(preview);
  if (rows.length === 0) return null;

  return (
    <div className="rounded-lg border border-border text-xs">
      <div className="border-b border-border bg-muted px-2 py-1 font-medium text-muted-foreground">
        On import
      </div>
      <table className="w-full">
        <tbody>
          {rows.map((r) => (
            <tr key={r.action} className="border-t border-border first:border-t-0">
              <td className="px-2 py-1">{r.action}</td>
              <td className="px-2 py-1 text-right font-medium tabular-nums">
                {r.count}
              </td>
              <td className="px-2 py-1 text-right">
                {r.gate === "BLOCK" && (
                  <span className="font-semibold text-destructive">BLOCK</span>
                )}
                {r.gate === "WARN" && (
                  <span className="font-semibold text-amber-600">WARN</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
