import { describe, it, expect, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { ReportTable } from "@/app/(dashboard)/teachers/productivity/_components/report-table";
import { ReportCards } from "@/app/(dashboard)/teachers/productivity/_components/report-cards";
import { ReportCharts } from "@/app/(dashboard)/teachers/productivity/_components/report-charts";
import type {
  ProductivityReportResponse,
  ProductivityReportTeacherRow,
} from "@/app/(dashboard)/teachers/productivity/_schemas/productivity-report";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
}));

function teacher(
  over: Partial<ProductivityReportTeacherRow>,
): ProductivityReportTeacherRow {
  return {
    teacher_id: "t1",
    first_name: "Asha",
    last_name: "Patil",
    scheduled: 10,
    conducted: 9,
    completion_pct: 90,
    hours: 12,
    minutes: 720,
    on_time_count: 8,
    late_count: 1,
    punctuality_pct: 89,
    avg_delay_min: 12,
    topics_planned: 6,
    topics_covered: 5,
    ...over,
  };
}

describe("Teacher productivity report", () => {
  beforeEach(() => push.mockReset());

  it("renders summary cards", () => {
    render(
      <ReportCards
        summary={{
          teachers: 3,
          total_scheduled: 30,
          total_conducted: 27,
          total_hours: 40,
          completion_pct: 90,
          punctuality_pct: 82,
        }}
      />,
    );
    expect(screen.getByText("Total scheduled")).toBeInTheDocument();
    expect(screen.getByText("30")).toBeInTheDocument();
    expect(screen.getByText("90%")).toBeInTheDocument();
  });

  it("sorts the teacher table by a column and drills down on row click", () => {
    const rows = [
      teacher({ teacher_id: "t1", last_name: "Low", scheduled: 5 }),
      teacher({ teacher_id: "t2", last_name: "High", scheduled: 20 }),
    ];
    render(<ReportTable rows={rows} />);

    // Default sort is scheduled desc → High (20) before Low (5).
    const bodyRows = screen.getAllByRole("row").slice(1); // drop header
    expect(within(bodyRows[0]).getByText(/High/)).toBeInTheDocument();

    // Toggle to ascending → Low first.
    fireEvent.click(screen.getByRole("button", { name: /Scheduled/ }));
    const asc = screen.getAllByRole("row").slice(1);
    expect(within(asc[0]).getByText(/Low/)).toBeInTheDocument();

    // Row click drills into the teacher's day-by-day log.
    fireEvent.click(within(asc[0]).getByText(/Low/));
    expect(push).toHaveBeenCalledWith("/teachers/t1");
  });

  it("renders charts with a metric toggle", () => {
    const report: ProductivityReportResponse = {
      from_date: null,
      to_date: null,
      summary: {
        teachers: 1,
        total_scheduled: 10,
        total_conducted: 9,
        total_hours: 12,
        completion_pct: 90,
        punctuality_pct: 89,
      },
      by_teacher: [teacher({})],
      by_subject: [
        {
          subject_id: "s1",
          subject_name: "Physics",
          scheduled: 10,
          conducted: 9,
          completion_pct: 90,
          hours: 12,
          minutes: 720,
        },
      ],
      by_batch: [
        {
          batch_id: "b1",
          batch_name: "11TH CET-1",
          scheduled: 10,
          conducted: 9,
          completion_pct: 90,
          hours: 12,
          minutes: 720,
        },
      ],
      trend: [
        {
          iso_year: 2026,
          iso_week: 34,
          label: "2026-W34",
          scheduled: 10,
          conducted: 9,
          completion_pct: 90,
          punctuality_pct: 89,
          hours: 12,
        },
      ],
    };
    render(<ReportCharts report={report} />);
    expect(screen.getByText("Scheduled vs Conducted")).toBeInTheDocument();
    expect(screen.getByText("Week-wise trend")).toBeInTheDocument();
    expect(screen.getByText("Physics")).toBeInTheDocument();
    expect(screen.getByText("11TH CET-1")).toBeInTheDocument();
  });
});
