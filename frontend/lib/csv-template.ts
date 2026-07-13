// Tiny helper for the "Download sample CSV" buttons on the bulk-import
// dialogs (lectures, students, teachers). Builds a CSV blob client-side
// and triggers a browser download — no backend round-trip needed since
// the column shape is already documented in each dialog.

// Neutralize spreadsheet formula injection: a cell a spreadsheet would treat as
// a formula gets a leading apostrophe so it's always rendered as text. This
// matters because exports now carry user-controlled data (student names, etc.);
// a name like `=HYPERLINK(...)` or `=cmd|...` would otherwise execute when the
// admin opens the file in Excel/Sheets. We guard `= + - @` plus the tab/CR that
// Excel trims to reveal a leading formula char (OWASP CSV-injection guidance).
function neutralizeFormula(v: string): string {
  return /^[=+\-@\t\r]/.test(v) ? `'${v}` : v;
}

// RFC 4180-style escape: neutralize formula triggers, then quote cells
// containing comma, quote, or newline.
export function csvCell(v: string): string {
  const safe = neutralizeFormula(v);
  return /[",\n]/.test(safe) ? `"${safe.replace(/"/g, '""')}"` : safe;
}

export function downloadCsvTemplate(
  filename: string,
  headers: string[],
  rows: string[][],
): void {
  const lines = [headers, ...rows].map((r) => r.map(csvCell).join(","));
  // UTF-8 BOM + CRLF so Excel on Windows opens the file cleanly.
  const blob = new Blob(["﻿" + lines.join("\r\n")], {
    type: "text/csv;charset=utf-8;",
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
