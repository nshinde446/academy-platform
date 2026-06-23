"use client";

import { useEffect, useState } from "react";
import apiClient from "@/services/api-client";
import { Button } from "@/components/ui/button";
import type {
  ImportColumnsResponse,
  ImportField,
} from "../_schemas/student";
import {
  type ColumnMap,
  loadMappingProfile,
  saveMappingProfile,
} from "../_lib/mapping-profile";

interface ColumnMapStepProps {
  branchId: string;
  file: File;
  onApply: (map: ColumnMap) => void;
  onCancel: () => void;
}

export function ColumnMapStep({
  branchId,
  file,
  onApply,
  onCancel,
}: ColumnMapStepProps) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [headers, setHeaders] = useState<string[]>([]);
  const [fields, setFields] = useState<ImportField[]>([]);
  // header -> field key ("" = ignore this column).
  const [map, setMap] = useState<Record<string, string>>({});
  const [saveProfile, setSaveProfile] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError("");
      try {
        const form = new FormData();
        form.append("file", file);
        const res = await apiClient.post<ImportColumnsResponse>(
          "/api/v1/students/import/columns",
          form,
          {
            params: { branch_id: branchId },
            headers: { "Content-Type": "multipart/form-data" },
          },
        );
        if (cancelled) return;
        setHeaders(res.data.headers);
        setFields(res.data.fields);
        // Start from the server's suggestion, then let a saved profile override
        // for any header it knows about.
        const saved = loadMappingProfile(branchId) ?? {};
        const initial: Record<string, string> = {};
        for (const h of res.data.headers) {
          initial[h] = saved[h] ?? res.data.suggested[h] ?? "";
        }
        setMap(initial);
      } catch (err: unknown) {
        if (!cancelled) setError("Could not read the file's columns.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [branchId, file]);

  function handleApply() {
    // Only keep columns that were actually mapped to a field.
    const cleaned: ColumnMap = {};
    for (const [header, fieldKey] of Object.entries(map)) {
      if (fieldKey) cleaned[header] = fieldKey;
    }
    if (saveProfile) saveMappingProfile(branchId, cleaned);
    onApply(cleaned);
  }

  const nameMapped = Object.values(map).includes("name");

  if (loading) {
    return (
      <p className="text-sm text-muted-foreground">Reading file columns…</p>
    );
  }
  if (error) {
    return (
      <div className="flex flex-col gap-2">
        <p className="text-sm text-destructive">{error}</p>
        <Button variant="outline" size="sm" onClick={onCancel}>
          Back
        </Button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm text-muted-foreground">
        Match each column in your file to a field. Unmatched columns are
        ignored. We remember this mapping for next time.
      </p>

      <div className="max-h-64 overflow-y-auto rounded-lg border border-border">
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-muted text-left text-muted-foreground">
            <tr>
              <th className="px-2 py-1 font-medium">Your column</th>
              <th className="px-2 py-1 font-medium">Maps to</th>
            </tr>
          </thead>
          <tbody>
            {headers.map((h) => (
              <tr key={h} className="border-t border-border">
                <td className="px-2 py-1 font-mono text-xs">{h}</td>
                <td className="px-2 py-1">
                  <select
                    aria-label={`Map column ${h}`}
                    className="h-8 w-full rounded-md border border-input bg-background px-2 text-xs"
                    value={map[h] ?? ""}
                    onChange={(e) =>
                      setMap((prev) => ({ ...prev, [h]: e.target.value }))
                    }
                  >
                    <option value="">— Ignore —</option>
                    {fields.map((f) => (
                      <option key={f.key} value={f.key}>
                        {f.label}
                        {f.required ? " *" : ""}
                      </option>
                    ))}
                  </select>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {!nameMapped && (
        <p className="text-xs text-amber-600">
          Map one column to <strong>Name</strong> — it&apos;s required.
        </p>
      )}

      <label className="flex items-center gap-2 text-xs text-muted-foreground">
        <input
          type="checkbox"
          checked={saveProfile}
          onChange={(e) => setSaveProfile(e.target.checked)}
        />
        Remember this mapping for future imports
      </label>

      <div className="flex justify-end gap-2">
        <Button variant="outline" size="sm" onClick={onCancel}>
          Back
        </Button>
        <Button size="sm" onClick={handleApply} disabled={!nameMapped}>
          Apply &amp; continue
        </Button>
      </div>
    </div>
  );
}
