"use client";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  CATEGORY_LABEL,
  EXAM_TYPE_LABEL,
  type ExamType,
} from "../_schemas/material";
import type { MaterialResponse } from "../_schemas/material";

interface PreviewProps {
  material: MaterialResponse | null;
  onIngest: (id: string) => void;
  onDelete: (id: string) => void;
  pending: boolean;
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function ingestBadgeTone(status: string) {
  switch (status) {
    case "ingested":
      return "success" as const;
    case "ingest_failed":
      return "destructive" as const;
    case "ingesting":
      return "warning" as const;
    case "archived":
      return "outline" as const;
    default:
      return "secondary" as const;
  }
}

export function MaterialPreviewPane({
  material,
  onIngest,
  onDelete,
  pending,
}: PreviewProps) {
  if (!material) {
    return (
      <div className="flex h-72 items-center justify-center rounded-xl border border-dashed bg-card p-4 text-center text-sm text-muted-foreground">
        Pick a material from the list to preview metadata and act on it.
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3 rounded-xl border bg-card p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="truncate text-sm font-semibold">
            {material.filename}
          </div>
          <div className="mt-0.5 text-[11px] text-muted-foreground">
            {formatSize(material.size_bytes)} · {material.mime_type}
          </div>
        </div>
        <Badge variant={ingestBadgeTone(material.ingest_status)}>
          {material.ingest_status}
        </Badge>
      </div>

      <dl className="grid grid-cols-[max-content_minmax(0,1fr)] gap-x-3 gap-y-1.5 text-[12.5px]">
        <dt className="text-muted-foreground">Class</dt>
        <dd className="font-medium">{material.class_label}</dd>

        <dt className="text-muted-foreground">Category</dt>
        <dd className="font-medium">{CATEGORY_LABEL[material.category]}</dd>

        {material.topic && (
          <>
            <dt className="text-muted-foreground">Topic</dt>
            <dd className="font-medium">{material.topic}</dd>
          </>
        )}

        <dt className="text-muted-foreground">Exam types</dt>
        <dd>
          {material.exam_types.length === 0 ? (
            <span className="text-muted-foreground">—</span>
          ) : (
            <div className="flex flex-wrap gap-1">
              {material.exam_types.map((e) => (
                <Badge key={e} variant="outline">
                  {EXAM_TYPE_LABEL[e as ExamType] ?? e}
                </Badge>
              ))}
            </div>
          )}
        </dd>

        <dt className="text-muted-foreground">Questions</dt>
        <dd className="font-medium tabular-nums">{material.question_count}</dd>

        <dt className="text-muted-foreground">Uploaded</dt>
        <dd className="text-muted-foreground">
          {new Date(material.created_at).toLocaleDateString()}
        </dd>
      </dl>

      {material.description && (
        <p className="rounded-md bg-muted/40 px-2.5 py-2 text-[12px] text-muted-foreground">
          {material.description}
        </p>
      )}

      {material.ingest_error && (
        <p className="rounded-md border border-destructive/30 bg-destructive/5 px-2.5 py-2 text-[12px] text-destructive">
          {material.ingest_error}
        </p>
      )}

      <div className="flex flex-wrap gap-2 pt-1">
        <Button
          size="sm"
          variant="outline"
          onClick={() => onIngest(material.id)}
          disabled={pending}
        >
          {material.ingest_status === "ingested" ? "Re-ingest" : "Ingest"}
        </Button>
        <Button
          size="sm"
          variant="outline"
          onClick={() => onDelete(material.id)}
          disabled={pending}
          className="ml-auto text-destructive hover:bg-destructive/10"
        >
          Delete
        </Button>
      </div>
    </div>
  );
}
