import { describe, it, expect, vi } from "vitest";
import { runBulkDelete, summarizeBulkDelete } from "@/lib/bulk-delete";

describe("runBulkDelete", () => {
  it("deletes every id when all succeed", async () => {
    const deleteOne = vi.fn().mockResolvedValue(undefined);
    const result = await runBulkDelete(["a", "b", "c"], deleteOne);
    expect(result.deleted).toBe(3);
    expect(result.failed).toEqual([]);
    expect(deleteOne).toHaveBeenCalledTimes(3);
  });

  it("collects failures with the server's reason message", async () => {
    const deleteOne = vi.fn(async (id: string) => {
      if (id === "b") {
        throw {
          response: { data: { detail: "has active batches" } },
        };
      }
    });
    const result = await runBulkDelete(["a", "b", "c"], deleteOne);
    expect(result.deleted).toBe(2);
    expect(result.failed).toEqual([{ id: "b", reason: "has active batches" }]);
  });

  it("prefers the structured error.message shape", async () => {
    const deleteOne = vi.fn(async () => {
      throw { response: { data: { error: { message: "nope" } } } };
    });
    const result = await runBulkDelete(["a"], deleteOne);
    expect(result.failed[0].reason).toBe("nope");
  });

  it("runs sequentially in id order", async () => {
    const order: string[] = [];
    const deleteOne = vi.fn(async (id: string) => {
      order.push(id);
    });
    await runBulkDelete(["x", "y", "z"], deleteOne);
    expect(order).toEqual(["x", "y", "z"]);
  });
});

describe("summarizeBulkDelete", () => {
  it("reports a clean all-success run", () => {
    expect(summarizeBulkDelete({ deleted: 3, failed: [] }, "course")).toBe(
      "Deleted 3 courses.",
    );
  });

  it("uses the singular noun for one", () => {
    expect(summarizeBulkDelete({ deleted: 1, failed: [] }, "course")).toBe(
      "Deleted 1 course.",
    );
  });

  it("groups skips by reason", () => {
    const summary = summarizeBulkDelete(
      {
        deleted: 1,
        failed: [
          { id: "a", reason: "has batches" },
          { id: "b", reason: "has batches" },
          { id: "c", reason: "locked" },
        ],
      },
      "course",
    );
    expect(summary).toBe(
      "Deleted 1 course, skipped 3: 2 (has batches), 1 (locked).",
    );
  });
});
