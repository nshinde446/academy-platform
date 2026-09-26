import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ReportTable } from "@/app/(dashboard)/teachers/productivity/_components/report-table";
import type { ProductivitySummaryRow } from "@/app/(dashboard)/teachers/productivity/_schemas/productivity-report";

function row(over: Partial<ProductivitySummaryRow>): ProductivitySummaryRow {
  return {
    emp_code: "0001",
    initials: "BD",
    teacher_name: "Bhagvat Dhesale",
    subject: "ENG",
    present_days: 20,
    total_lectures: 12,
    scheduled_minutes: 600,
    delivered_minutes: 600,
    ...over,
  };
}

describe("Teacher productivity summary table", () => {
  it("renders the document columns", () => {
    render(
      <ReportTable
        rows={[
          row({}),
          row({
            emp_code: "0004",
            initials: "SS",
            teacher_name: "Sagar Shahane",
            subject: "BIO",
          }),
        ]}
      />,
    );
    for (const h of [
      "Sr No",
      "Employee Code",
      "Initials",
      "Teacher",
      "Subject",
      "Present Days",
      "Total Lectures",
      "Scheduled Hours",
      "Delivered Hours",
    ]) {
      expect(screen.getByText(h)).toBeInTheDocument();
    }
    expect(screen.getByText("BD")).toBeInTheDocument();
    expect(screen.getByText("Bhagvat Dhesale")).toBeInTheDocument();
    // Hours formatted as "H Hours M Mins".
    expect(screen.getAllByText("10 Hours 0 Mins").length).toBeGreaterThan(0);
  });

  it("numbers rows sequentially in Sr No", () => {
    render(
      <ReportTable
        rows={[row({ emp_code: "A" }), row({ emp_code: "B" }), row({ emp_code: "C" })]}
      />,
    );
    // Sr No cells 1, 2, 3 are present.
    for (const n of ["1", "2", "3"]) {
      expect(screen.getAllByText(n).length).toBeGreaterThan(0);
    }
  });
});
