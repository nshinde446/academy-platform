import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  MaterialGridCard,
  MaterialStatusBadge,
} from "@/app/(dashboard)/materials/_components/list-row";
import type { MaterialResponse } from "@/app/(dashboard)/materials/_schemas/material";

function material(over: Partial<MaterialResponse> = {}): MaterialResponse {
  return {
    id: "m1",
    filename: "Kinematics-DPP-01.pdf",
    storage_key: "k",
    mime_type: "application/pdf",
    size_bytes: 2 * 1024 * 1024,
    sha256: "x",
    academic_year_id: "ay1",
    class_label: "12",
    subject_id: "s1",
    topic: null,
    category: "dpp",
    exam_types: ["neet"],
    description: null,
    ingest_status: "ingested",
    ingest_error: null,
    ingest_pages_total: null,
    ingest_pages_done: null,
    question_count: 12,
    branch_id: "br1",
    created_at: "2026-06-20T09:00:00Z",
    updated_at: "2026-06-20T09:00:00Z",
    created_by: null,
    ...over,
  };
}

describe("MaterialGridCard", () => {
  it("renders filename, category, status, and question count", () => {
    render(
      <MaterialGridCard material={material()} selected={false} onSelect={() => {}} />,
    );
    expect(screen.getByText("Kinematics-DPP-01.pdf")).toBeInTheDocument();
    expect(screen.getByText("DPP")).toBeInTheDocument();
    expect(screen.getByText("Ingested")).toBeInTheDocument();
    expect(screen.getByText(/12 questions/)).toBeInTheDocument();
  });

  it("calls onSelect with the material id when clicked", async () => {
    const onSelect = vi.fn();
    const user = userEvent.setup();
    render(
      <MaterialGridCard material={material()} selected={false} onSelect={onSelect} />,
    );
    await user.click(screen.getByText("Kinematics-DPP-01.pdf"));
    expect(onSelect).toHaveBeenCalledWith("m1");
  });
});

describe("MaterialStatusBadge", () => {
  it("maps each ingest status to its label", () => {
    const { rerender } = render(<MaterialStatusBadge status="uploaded" />);
    expect(screen.getByText("New")).toBeInTheDocument();
    rerender(<MaterialStatusBadge status="ingesting" />);
    expect(screen.getByText("Extracting…")).toBeInTheDocument();
    rerender(<MaterialStatusBadge status="ingest_failed" />);
    expect(screen.getByText("Failed")).toBeInTheDocument();
  });
});
