import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ColumnMapStep } from "@/app/(dashboard)/students/_components/column-map-step";
import apiClient from "@/services/api-client";

vi.mock("@/services/api-client", () => ({
  default: { post: vi.fn() },
}));

const post = apiClient.post as ReturnType<typeof vi.fn>;

const COLUMNS = {
  data: {
    headers: ["Student Name", "Std", "Group"],
    suggested: { "Student Name": null, Std: null, Group: "batch" },
    fields: [
      { key: "name", label: "Name", required: "1" },
      { key: "class", label: "Class" },
      { key: "batch", label: "Batch" },
    ],
  },
};

beforeEach(() => {
  localStorage.clear();
  post.mockReset();
});

function file() {
  return new File(["x"], "roster.csv", { type: "text/csv" });
}

describe("ColumnMapStep", () => {
  it("seeds dropdowns from the server suggestion", async () => {
    post.mockResolvedValueOnce(COLUMNS);
    render(
      <ColumnMapStep
        branchId="b1"
        file={file()}
        onApply={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    const groupSel = (await screen.findByRole("combobox", {
      name: /map column group/i,
    })) as HTMLSelectElement;
    expect(groupSel.value).toBe("batch"); // suggested
  });

  it("blocks Apply until a Name column is mapped", async () => {
    post.mockResolvedValueOnce(COLUMNS);
    const onApply = vi.fn();
    render(
      <ColumnMapStep
        branchId="b1"
        file={file()}
        onApply={onApply}
        onCancel={vi.fn()}
      />,
    );
    const apply = await screen.findByRole("button", {
      name: /apply & continue/i,
    });
    expect(apply).toBeDisabled();

    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: /map column student name/i }),
      "name",
    );
    expect(apply).toBeEnabled();
    await userEvent.click(apply);
    expect(onApply).toHaveBeenCalledWith({
      "Student Name": "name",
      Group: "batch",
    });
  });

  it("persists and re-applies a saved profile", async () => {
    localStorage.setItem(
      "students:column-map:b1",
      JSON.stringify({ "Student Name": "name" }),
    );
    post.mockResolvedValueOnce(COLUMNS);
    render(
      <ColumnMapStep
        branchId="b1"
        file={file()}
        onApply={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    const nameSel = (await screen.findByRole("combobox", {
      name: /map column student name/i,
    })) as HTMLSelectElement;
    // Saved profile overrides the (null) suggestion.
    await waitFor(() => expect(nameSel.value).toBe("name"));
  });
});
