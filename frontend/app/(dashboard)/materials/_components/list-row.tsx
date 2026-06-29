"use client";

import { Badge } from "@/components/ui/badge";
import { CATEGORY_LABEL } from "../_schemas/material";
import type { IngestStatus, MaterialResponse } from "../_schemas/material";

interface ListRowProps {
  material: MaterialResponse;
  selected: boolean;
  onSelect: (id: string) => void;
  isLast?: boolean;
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// Ingest lifecycle -> badge. Mirrors the MSA console's status chips.
const STATUS_META: Record<
  IngestStatus,
  { label: string; tone: "success" | "warning" | "destructive" | "secondary" }
> = {
  uploaded: { label: "New", tone: "secondary" },
  ingesting: { label: "Extracting…", tone: "warning" },
  ingested: { label: "Ingested", tone: "success" },
  ingest_failed: { label: "Failed", tone: "destructive" },
  archived: { label: "Archived", tone: "secondary" },
};

export function MaterialStatusBadge({ status }: { status: IngestStatus }) {
  const meta = STATUS_META[status] ?? STATUS_META.uploaded;
  return (
    <Badge variant={meta.tone} className="shrink-0">
      {meta.label}
    </Badge>
  );
}

function MetaLine({ material }: { material: MaterialResponse }) {
  return (
    <div className="flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
      <span>Class {material.class_label}</span>
      <span>·</span>
      <span>{formatSize(material.size_bytes)}</span>
      <span>·</span>
      <span>
        {material.question_count} question
        {material.question_count !== 1 ? "s" : ""}
      </span>
      {material.exam_types.length > 0 && (
        <>
          <span>·</span>
          <span>{material.exam_types.join(" / ")}</span>
        </>
      )}
    </div>
  );
}

export function MaterialListRow({
  material,
  selected,
  onSelect,
  isLast,
}: ListRowProps) {
  return (
    <button
      type="button"
      onClick={() => onSelect(material.id)}
      className={`flex w-full items-start gap-3 border-b px-3 py-2.5 text-left transition-colors ${
        isLast ? "border-b-0" : ""
      } ${selected ? "bg-primary/5" : "hover:bg-muted/40"}`}
    >
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <div className="flex items-center gap-2">
          <span className="truncate text-sm font-medium">
            {material.filename}
          </span>
          <Badge variant="outline" className="shrink-0">
            {CATEGORY_LABEL[material.category]}
          </Badge>
          <MaterialStatusBadge status={material.ingest_status} />
        </div>
        <MetaLine material={material} />
      </div>
    </button>
  );
}

// Grid variant — the same material as a card, for the List/Grid toggle.
export function MaterialGridCard({
  material,
  selected,
  onSelect,
}: Omit<ListRowProps, "isLast">) {
  return (
    <button
      type="button"
      onClick={() => onSelect(material.id)}
      className={`flex h-full flex-col gap-2 rounded-xl border bg-card p-3 text-left transition-colors ${
        selected
          ? "border-primary/40 ring-1 ring-primary/30"
          : "hover:border-foreground/20 hover:bg-muted/30"
      }`}
    >
      <div className="flex items-center justify-between gap-2">
        <Badge variant="outline" className="shrink-0">
          {CATEGORY_LABEL[material.category]}
        </Badge>
        <MaterialStatusBadge status={material.ingest_status} />
      </div>
      <span className="line-clamp-2 text-sm font-medium leading-snug">
        {material.filename}
      </span>
      <div className="mt-auto">
        <MetaLine material={material} />
      </div>
    </button>
  );
}
