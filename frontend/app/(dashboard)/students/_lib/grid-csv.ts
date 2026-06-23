// T4 — turn the edited grid rows back into a CSV so the existing import
// pipeline (background job + partial-accept + undo) can consume them. Headers
// are the canonical field keys, which the importer already recognizes, so no
// column map is needed on the way back in.

import { csvCell, downloadCsvTemplate } from "@/lib/csv-template";
import type { ImportParseRow } from "../_schemas/student";

function toMatrix(fields: string[], rows: ImportParseRow[]): string[][] {
  return rows.map((r) => fields.map((f) => r.values[f] ?? ""));
}

export function rowsToCsvFile(
  fields: string[],
  rows: ImportParseRow[],
  filename: string,
): File {
  const lines = [fields, ...toMatrix(fields, rows)].map((r) =>
    r.map(csvCell).join(","),
  );
  const blob = "﻿" + lines.join("\r\n");
  return new File([blob], filename, { type: "text/csv" });
}

export function downloadRows(
  fields: string[],
  rows: ImportParseRow[],
  filename: string,
): void {
  downloadCsvTemplate(filename, fields, toMatrix(fields, rows));
}
