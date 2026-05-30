// Tiny helper for the "Download sample CSV" buttons on the bulk-import
// dialogs (lectures, students, teachers). Builds a CSV blob client-side
// and triggers a browser download — no backend round-trip needed since
// the column shape is already documented in each dialog.

// RFC 4180-style escape: quote cells containing comma, quote, or newline.
export function csvCell(v: string): string {
  return /[",\n]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v;
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
