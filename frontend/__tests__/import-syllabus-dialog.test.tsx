import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ImportSyllabusDialog } from "@/app/(dashboard)/syllabus/_components/import-syllabus-dialog";
import type {
  CourseOption,
  SyllabusImportSummary,
} from "@/app/(dashboard)/syllabus/_schemas/syllabus";

const COURSES: CourseOption[] = [
  { id: "c1", name: "NEET 2-Year", code: "NEET-2Y", duration_years: 2 },
  { id: "c2", name: "Class 9", code: "C9", duration_years: 1 },
];

function setFile(input: HTMLInputElement, file: File) {
  Object.defineProperty(input, "files", {
    value: [file],
    configurable: true,
  });
  fireEvent.change(input);
}

function submitForm() {
  // The dialog's form lives in a portal; reach it via any of its inputs.
  const anyField = screen.getByLabelText(/course \*/i);
  const form = anyField.closest("form");
  if (!form) throw new Error("No <form> ancestor for the dialog");
  fireEvent.submit(form);
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("ImportSyllabusDialog", () => {
  it("disables the trigger when there are no courses", () => {
    render(
      <ImportSyllabusDialog
        courses={[]}
        onImport={vi.fn()}
        isPending={false}
      />
    );
    expect(
      screen.getByRole("button", { name: /import syllabus/i })
    ).toBeDisabled();
  });

  it("opens, pre-selects the default course, and lists all courses", async () => {
    const user = userEvent.setup();
    render(
      <ImportSyllabusDialog
        courses={COURSES}
        defaultCourseId="c2"
        onImport={vi.fn()}
        isPending={false}
      />
    );

    await user.click(
      screen.getByRole("button", { name: /import syllabus/i })
    );

    const courseSelect = screen.getByLabelText(/course \*/i) as HTMLSelectElement;
    expect(courseSelect.value).toBe("c2");
    expect(
      screen.getByRole("option", { name: /neet 2-year/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("option", { name: /class 9/i })
    ).toBeInTheDocument();
  });

  it("shows an error and skips onImport when no file is picked", async () => {
    const user = userEvent.setup();
    const onImport = vi.fn();
    render(
      <ImportSyllabusDialog
        courses={COURSES}
        defaultCourseId="c1"
        onImport={onImport}
        isPending={false}
      />
    );
    await user.click(
      screen.getByRole("button", { name: /import syllabus/i })
    );
    submitForm();

    await waitFor(() => {
      expect(screen.getByText(/pick an \.xlsx/i)).toBeInTheDocument();
    });
    expect(onImport).not.toHaveBeenCalled();
  });

  it("rejects non-.xlsx files with a friendly error", async () => {
    const user = userEvent.setup();
    const onImport = vi.fn();
    render(
      <ImportSyllabusDialog
        courses={COURSES}
        defaultCourseId="c1"
        onImport={onImport}
        isPending={false}
      />
    );

    await user.click(
      screen.getByRole("button", { name: /import syllabus/i })
    );

    const input = screen.getByLabelText(/file \(\.xlsx\)/i) as HTMLInputElement;
    setFile(input, new File(["a,b"], "syllabus.csv"));

    submitForm();

    await waitFor(() => {
      expect(screen.getByText(/only \.xlsx/i)).toBeInTheDocument();
    });
    expect(onImport).not.toHaveBeenCalled();
  });

  it("calls onImport with course + file when both are set", async () => {
    const user = userEvent.setup();
    const summary: SyllabusImportSummary = {
      subjects_created: 3,
      chapters_created: 12,
      topics_created: 40,
      subtopics_created: 80,
      rows_processed: 120,
      errors: [],
    };
    const onImport = vi.fn().mockResolvedValue(summary);

    render(
      <ImportSyllabusDialog
        courses={COURSES}
        defaultCourseId="c1"
        onImport={onImport}
        isPending={false}
      />
    );

    await user.click(
      screen.getByRole("button", { name: /import syllabus/i })
    );

    const input = screen.getByLabelText(/file \(\.xlsx\)/i) as HTMLInputElement;
    setFile(input, new File(["dummy"], "syllabus.xlsx"));

    submitForm();

    await waitFor(() => {
      expect(onImport).toHaveBeenCalledTimes(1);
    });
    const call = onImport.mock.calls[0][0];
    expect(call.courseId).toBe("c1");
    expect(call.file.name).toBe("syllabus.xlsx");

    await waitFor(() => {
      expect(screen.getByTestId("import-summary")).toBeInTheDocument();
    });
    expect(screen.getByText(/rows processed: 120/i)).toBeInTheDocument();
    expect(screen.getByText(/subtopics created: 80/i)).toBeInTheDocument();
  });

  it("surfaces a backend error message from the rejection", async () => {
    const user = userEvent.setup();
    const onImport = vi.fn().mockRejectedValue({
      response: { data: { detail: "Course not found." } },
    });

    render(
      <ImportSyllabusDialog
        courses={COURSES}
        defaultCourseId="c1"
        onImport={onImport}
        isPending={false}
      />
    );

    await user.click(
      screen.getByRole("button", { name: /import syllabus/i })
    );

    const input = screen.getByLabelText(/file \(\.xlsx\)/i) as HTMLInputElement;
    setFile(input, new File(["dummy"], "syllabus.xlsx"));

    submitForm();

    await waitFor(() => {
      expect(screen.getByText(/course not found/i)).toBeInTheDocument();
    });
  });
});
