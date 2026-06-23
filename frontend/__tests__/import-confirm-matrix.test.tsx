import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ImportConfirmMatrix } from "@/app/(dashboard)/students/_components/import-confirm-matrix";
import type { ImportPreview } from "@/app/(dashboard)/students/_schemas/student";

function preview(over: Partial<ImportPreview> = {}): ImportPreview {
  return {
    total_rows: 3,
    importable_rows: 3,
    rows_missing_name: 0,
    rows_invalid_enrolment: 0,
    rows_invalid_consistency: 0,
    rows_with_warnings: 0,
    rows_possible_duplicate: 0,
    duplicate_rows: 0,
    unbatched_rows: 0,
    existing_batches: 0,
    missing_batches: 0,
    blocked_batches: 0,
    blocking_error: null,
    new_academic_years: [],
    batches: [],
    row_issues: [],
    unrecognized_columns: [],
    ...over,
  };
}

const batch = (over: Record<string, unknown>) => ({
  code: "NEET-11-A",
  student_count: 2,
  exists: false,
  target: "NEET",
  suggested_course_code: "NEET",
  suggested_course_name: "NEET Preparation",
  suggested_exam_date: "2026-05-04",
  creatable: true,
  blocker: null,
  ...over,
});

describe("ImportConfirmMatrix", () => {
  it("renders nothing when there is nothing to report", () => {
    const { container } = render(<ImportConfirmMatrix preview={preview()} />);
    expect(container.firstChild).toBeNull();
  });

  it("summarizes new courses, batches and academic years", () => {
    render(
      <ImportConfirmMatrix
        preview={preview({
          batches: [
            batch({ code: "NEET-11-A" }),
            batch({ code: "JEE-12-B", suggested_course_code: "JEE" }),
            batch({ code: "OLD-1", exists: true, creatable: false }),
          ],
          new_academic_years: ["2026-27", "2027-28"],
        })}
      />,
    );
    expect(screen.getByText("New courses")).toBeInTheDocument();
    expect(screen.getByText("New batches")).toBeInTheDocument();
    expect(screen.getByText("Existing batches matched")).toBeInTheDocument();
    expect(screen.getByText("New academic years")).toBeInTheDocument();
  });

  it("flags blocked batches as BLOCK and possible duplicates as WARN", () => {
    render(
      <ImportConfirmMatrix
        preview={preview({ blocked_batches: 1, rows_possible_duplicate: 2 })}
      />,
    );
    expect(screen.getByText("BLOCK")).toBeInTheDocument();
    expect(screen.getByText("WARN")).toBeInTheDocument();
  });
});
