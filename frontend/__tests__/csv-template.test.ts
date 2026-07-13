import { describe, it, expect, vi, beforeEach } from "vitest";
import { csvCell, downloadCsvTemplate } from "@/lib/csv-template";

describe("csvCell", () => {
  it("leaves a plain cell unquoted", () => {
    expect(csvCell("hello")).toBe("hello");
  });

  it("quotes a cell with a comma", () => {
    expect(csvCell("a, b")).toBe('"a, b"');
  });

  it("quotes a cell with a newline", () => {
    expect(csvCell("line1\nline2")).toBe('"line1\nline2"');
  });

  it("escapes internal quotes by doubling them", () => {
    expect(csvCell('he said "hi"')).toBe('"he said ""hi"""');
  });

  it("neutralizes a leading formula character with an apostrophe", () => {
    expect(csvCell("=HYPERLINK(1)")).toBe("'=HYPERLINK(1)");
    expect(csvCell("+1")).toBe("'+1");
    expect(csvCell("-2+3")).toBe("'-2+3");
    expect(csvCell("@cmd")).toBe("'@cmd");
  });

  it("neutralizes a tab/CR that hides a leading formula", () => {
    expect(csvCell("\t=1")).toBe("'\t=1");
    expect(csvCell("\r=1")).toBe("'\r=1");
  });

  it("still quotes a neutralized cell that also has a comma", () => {
    // `=cmd,1` → prefixed to `'=cmd,1`, then quoted for the comma.
    expect(csvCell("=cmd,1")).toBe(`"'=cmd,1"`);
  });

  it("does not touch a value with a formula char mid-string", () => {
    expect(csvCell("A=B")).toBe("A=B");
    expect(csvCell("Rao")).toBe("Rao");
  });
});

describe("downloadCsvTemplate", () => {
  let createObjectURL: ReturnType<typeof vi.fn>;
  let revokeObjectURL: ReturnType<typeof vi.fn>;
  let capturedBlob: Blob | null;
  let clickSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    capturedBlob = null;
    createObjectURL = vi.fn((b: Blob) => {
      capturedBlob = b;
      return "blob:mock";
    });
    revokeObjectURL = vi.fn();
    URL.createObjectURL = createObjectURL as typeof URL.createObjectURL;
    URL.revokeObjectURL = revokeObjectURL as typeof URL.revokeObjectURL;
    clickSpy = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(() => {});
  });

  it("builds a CSV with headers + rows and triggers a download", async () => {
    downloadCsvTemplate(
      "sample.csv",
      ["a", "b", "c"],
      [
        ["1", "two", "three"],
        ["4", "5,6", '7"x'],
      ],
    );

    expect(clickSpy).toHaveBeenCalled();
    expect(createObjectURL).toHaveBeenCalled();
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:mock");

    const text = await (capturedBlob as unknown as Blob).text();
    // Header row first.
    expect(text).toContain("a,b,c");
    // Simple row.
    expect(text).toContain("1,two,three");
    // Comma + quote escapes survive.
    expect(text).toContain('"5,6"');
    expect(text).toContain('"7""x"');
    // CRLF line endings.
    expect(text).toContain("\r\n");
  });
});
