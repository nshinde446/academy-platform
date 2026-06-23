"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import apiClient from "@/services/api-client";
import { Button } from "@/components/ui/button";
import type {
  ImportField,
  ImportParseResponse,
  ImportParseRow,
  ImportRowValidation,
} from "../_schemas/student";
import { rowsToCsvFile, downloadRows } from "../_lib/grid-csv";

interface ValidationGridStepProps {
  branchId: string;
  file: File;
  columnMap: Record<string, string> | null;
  // Hand a CSV of the chosen rows back to the dialog's normal import flow.
  onImport: (csvFile: File, createMissing: boolean) => void;
  onBack: () => void;
}

// Render is capped so a huge upload can't lock the tab; the cap covers the
// fix-the-bad-rows workflow (problem rows are sorted to the top).
const RENDER_CAP = 400;

export function ValidationGridStep({
  branchId,
  file,
  columnMap,
  onImport,
  onBack,
}: ValidationGridStepProps) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [fields, setFields] = useState<string[]>([]);
  const [labels, setLabels] = useState<Record<string, string>>({});
  const [rows, setRows] = useState<ImportParseRow[]>([]);
  const [validation, setValidation] = useState<
    Record<number, ImportRowValidation>
  >({});
  const [createMissing, setCreateMissing] = useState(false);
  const [validating, setValidating] = useState(false);
  const debounce = useRef<ReturnType<typeof setTimeout> | null>(null);

  function indexValidation(list: ImportRowValidation[]) {
    const map: Record<number, ImportRowValidation> = {};
    for (const v of list) map[v.index] = v;
    return map;
  }

  // Initial parse + validation.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError("");
      try {
        const form = new FormData();
        form.append("file", file);
        if (columnMap && Object.keys(columnMap).length > 0) {
          form.append("column_map", JSON.stringify(columnMap));
        }
        const res = await apiClient.post<ImportParseResponse>(
          "/api/v1/students/import/parse",
          form,
          {
            params: { branch_id: branchId, create_missing_batches: createMissing },
            headers: { "Content-Type": "multipart/form-data" },
          },
        );
        if (cancelled) return;
        setFields(res.data.fields);
        setLabels(
          Object.fromEntries(
            res.data.import_fields.map((f: ImportField) => [f.key, f.label]),
          ),
        );
        setRows(res.data.rows);
        setValidation(indexValidation(res.data.validation));
      } catch {
        if (!cancelled) setError("Could not read the file.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
    // Re-parse only on file/branch change; createMissing re-validates via revalidate().
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [branchId, file]);

  async function revalidate(nextRows: ImportParseRow[], nextCreate: boolean) {
    setValidating(true);
    try {
      const res = await apiClient.post<{ validation: ImportRowValidation[] }>(
        "/api/v1/students/import/validate",
        {
          rows: nextRows.map((r) => r.values),
          create_missing_batches: nextCreate,
        },
        { params: { branch_id: branchId } },
      );
      setValidation(indexValidation(res.data.validation));
    } catch {
      /* keep the last validation on a transient failure */
    } finally {
      setValidating(false);
    }
  }

  function scheduleRevalidate(nextRows: ImportParseRow[], nextCreate: boolean) {
    if (debounce.current) clearTimeout(debounce.current);
    debounce.current = setTimeout(() => revalidate(nextRows, nextCreate), 400);
  }

  function editCell(index: number, field: string, value: string) {
    setRows((prev) => {
      const next = prev.map((r) =>
        r.index === index ? { ...r, values: { ...r.values, [field]: value } } : r,
      );
      scheduleRevalidate(next, createMissing);
      return next;
    });
  }

  function toggleCreateMissing(value: boolean) {
    setCreateMissing(value);
    revalidate(rows, value);
  }

  const validRows = useMemo(
    () => rows.filter((r) => (validation[r.index]?.errors.length ?? 0) === 0),
    [rows, validation],
  );
  const invalidRows = useMemo(
    () => rows.filter((r) => (validation[r.index]?.errors.length ?? 0) > 0),
    [rows, validation],
  );

  // Problem rows first so the fix workflow is front-and-centre under the cap.
  const ordered = useMemo(() => {
    const score = (r: ImportParseRow) => {
      const v = validation[r.index];
      if (v?.errors.length) return 0;
      if (v?.warnings.length) return 1;
      return 2;
    };
    return [...rows].sort((a, b) => score(a) - score(b)).slice(0, RENDER_CAP);
  }, [rows, validation]);

  function handleImport() {
    if (validRows.length === 0) return;
    onImport(rowsToCsvFile(fields, validRows, "import.csv"), createMissing);
  }

  function handleDownloadInvalid() {
    downloadRows(fields, invalidRows, "rejected-rows.csv");
  }

  if (loading) {
    return <p className="text-sm text-muted-foreground">Reading rows…</p>;
  }
  if (error) {
    return (
      <div className="flex flex-col gap-2">
        <p className="text-sm text-destructive">{error}</p>
        <Button variant="outline" size="sm" onClick={onBack}>
          Back
        </Button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
        <span>
          <span className="font-medium text-emerald-600">
            {validRows.length} ready
          </span>{" "}
          ·{" "}
          <span className="font-medium text-destructive">
            {invalidRows.length} need fixing
          </span>{" "}
          · {rows.length} total
          {validating && (
            <span className="ml-2 text-xs text-muted-foreground">checking…</span>
          )}
        </span>
        <label className="flex items-center gap-1.5 text-xs">
          <input
            type="checkbox"
            checked={createMissing}
            onChange={(e) => toggleCreateMissing(e.target.checked)}
          />
          Create missing batches
        </label>
      </div>

      <div className="max-h-80 overflow-auto rounded-lg border border-border">
        <table className="w-full border-collapse text-xs">
          <thead className="sticky top-0 bg-muted text-left text-muted-foreground">
            <tr>
              <th className="px-2 py-1 font-medium">#</th>
              {fields.map((f) => (
                <th key={f} className="px-2 py-1 font-medium whitespace-nowrap">
                  {labels[f] ?? f}
                </th>
              ))}
              <th className="px-2 py-1 font-medium">Issues</th>
            </tr>
          </thead>
          <tbody>
            {ordered.map((r) => {
              const v = validation[r.index];
              const hasError = (v?.errors.length ?? 0) > 0;
              const hasWarn = !hasError && (v?.warnings.length ?? 0) > 0;
              return (
                <tr
                  key={r.index}
                  className={
                    "border-t border-border " +
                    (hasError
                      ? "bg-destructive/5"
                      : hasWarn
                        ? "bg-amber-500/5"
                        : "")
                  }
                >
                  <td className="px-2 py-1 tabular-nums text-muted-foreground">
                    {r.row_number}
                  </td>
                  {fields.map((f) => (
                    <td key={f} className="px-1 py-0.5">
                      <input
                        aria-label={`${labels[f] ?? f} row ${r.row_number}`}
                        className="h-7 w-full min-w-24 rounded border border-input bg-background px-1.5"
                        value={r.values[f] ?? ""}
                        onChange={(e) => editCell(r.index, f, e.target.value)}
                      />
                    </td>
                  ))}
                  <td className="px-2 py-1">
                    {hasError && (
                      <span className="text-destructive">
                        {v!.errors.join("; ")}
                      </span>
                    )}
                    {hasWarn && (
                      <span className="text-amber-600">
                        {v!.warnings.join("; ")}
                      </span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {rows.length > RENDER_CAP && (
        <p className="text-xs text-muted-foreground">
          Showing the {RENDER_CAP} rows most needing attention of {rows.length}.
          The rest import as-is.
        </p>
      )}

      <div className="flex flex-wrap justify-end gap-2">
        <Button variant="outline" size="sm" onClick={onBack}>
          Back
        </Button>
        {invalidRows.length > 0 && (
          <Button variant="outline" size="sm" onClick={handleDownloadInvalid}>
            Download {invalidRows.length} rejected
          </Button>
        )}
        <Button
          size="sm"
          onClick={handleImport}
          disabled={validRows.length === 0}
        >
          Import {validRows.length} ready row(s)
        </Button>
      </div>
    </div>
  );
}
