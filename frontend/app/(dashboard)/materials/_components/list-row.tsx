"use client";

import { Badge } from "@/components/ui/badge";
import { CATEGORY_LABEL } from "../_schemas/material";
import type { MaterialResponse } from "../_schemas/material";

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
        </div>
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
      </div>
    </button>
  );
}
