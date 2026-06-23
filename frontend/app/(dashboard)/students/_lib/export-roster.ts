// T9 — export the current roster view (respecting the active search/sort, and
// later filters) to a CSV the admin can edit offline and re-import. The roster
// endpoint caps a page at 200 rows, so we loop pages until every matching row
// is pulled, then build the file client-side via the shared CSV helper.

import apiClient from "@/services/api-client";
import { downloadCsvTemplate } from "@/lib/csv-template";
import type { StudentStatsPage, StudentWithStats } from "../_schemas/student";

const EXPORT_PAGE = 200;

export interface RosterQuery {
  search: string;
  sortBy?: string;
  order?: "asc" | "desc";
  standard?: string;
  targetExam?: string;
  feesStatus?: string;
  batchId?: string;
}

/** Pull every roster row matching the query, paging at the endpoint's cap. */
export async function fetchAllRoster(
  branchId: string,
  query: RosterQuery,
): Promise<StudentWithStats[]> {
  const all: StudentWithStats[] = [];
  let offset = 0;
  for (;;) {
    const res = await apiClient.get<StudentStatsPage>(
      "/api/v1/students/roster",
      {
        params: {
          branch_id: branchId,
          offset,
          limit: EXPORT_PAGE,
          search: query.search || undefined,
          sort_by: query.sortBy,
          order: query.order,
          standard: query.standard || undefined,
          target_exam: query.targetExam || undefined,
          fees_status: query.feesStatus || undefined,
          batch_id: query.batchId || undefined,
        },
      },
    );
    all.push(...res.data.items);
    offset += EXPORT_PAGE;
    if (res.data.items.length === 0 || offset >= res.data.total) break;
  }
  return all;
}

const EXPORT_HEADERS = [
  "Name",
  "Enrollment",
  "Class",
  "Target",
  "Stream",
  "Batch",
  "Batch rank",
  "Avg score %",
  "Attendance %",
  "DPP %",
  "Fees",
  "Tests taken",
];

export function rosterToRows(rows: StudentWithStats[]): string[][] {
  return rows.map((r) => [
    `${r.first_name} ${r.last_name}`.trim(),
    r.enrollment_number ?? "",
    r.standard ?? "",
    r.target_exam ?? "",
    r.stream ?? "",
    r.batch_name ?? "",
    r.batch_rank != null ? String(r.batch_rank) : "",
    r.avg_score_pct.toFixed(0),
    r.attendance_pct.toFixed(0),
    r.dpp_completion_pct.toFixed(0),
    r.fees_status ?? "",
    String(r.tests_taken),
  ]);
}

/** Download an already-in-hand set of roster rows (e.g. the current selection). */
export function downloadRosterRows(rows: StudentWithStats[]): void {
  const stamp = new Date().toISOString().slice(0, 10);
  downloadCsvTemplate(
    `students-selected-${stamp}.csv`,
    EXPORT_HEADERS,
    rosterToRows(rows),
  );
}

/** Fetch the full current view and trigger a CSV download. Returns the count. */
export async function exportRosterCsv(
  branchId: string,
  query: RosterQuery,
): Promise<number> {
  const rows = await fetchAllRoster(branchId, query);
  const stamp = new Date().toISOString().slice(0, 10);
  downloadCsvTemplate(
    `students-${stamp}.csv`,
    EXPORT_HEADERS,
    rosterToRows(rows),
  );
  return rows.length;
}
