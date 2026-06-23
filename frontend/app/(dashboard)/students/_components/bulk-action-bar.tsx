"use client";

import { Button } from "@/components/ui/button";
import { STANDARDS, STREAMS } from "../_schemas/student";

const FEES_OPTIONS = ["paid", "due", "overdue", "partial"] as const;

interface BatchOption {
  id: string;
  code: string;
}

interface BulkActionBarProps {
  count: number;
  batches: BatchOption[];
  pending: boolean;
  onSetFees: (value: string) => void;
  onSetClass: (value: string) => void;
  onSetStream: (value: string) => void;
  onAssignBatch: (batchId: string) => void;
  onExport: () => void;
  onDelete: () => void;
  onClear: () => void;
}

// Reusable "action select" — fires its handler on pick, then snaps back to the
// label so it always reads as a command rather than a value.
function ActionSelect({
  label,
  options,
  onPick,
  disabled,
}: {
  label: string;
  options: { value: string; label: string }[];
  onPick: (value: string) => void;
  disabled: boolean;
}) {
  return (
    <select
      aria-label={label}
      disabled={disabled}
      value=""
      onChange={(e) => {
        if (e.target.value) onPick(e.target.value);
        e.currentTarget.value = "";
      }}
      className="h-9 rounded-md border border-input bg-background px-2 text-sm disabled:opacity-50"
    >
      <option value="">{label}</option>
      {options.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  );
}

export function BulkActionBar({
  count,
  batches,
  pending,
  onSetFees,
  onSetClass,
  onSetStream,
  onAssignBatch,
  onExport,
  onDelete,
  onClear,
}: BulkActionBarProps) {
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-lg border border-primary/30 bg-primary/5 px-3 py-2">
      <span className="text-sm font-medium">
        {count} selected
      </span>
      <ActionSelect
        label="Set fees"
        disabled={pending}
        onPick={onSetFees}
        options={FEES_OPTIONS.map((f) => ({
          value: f,
          label: f[0].toUpperCase() + f.slice(1),
        }))}
      />
      <ActionSelect
        label="Set class"
        disabled={pending}
        onPick={onSetClass}
        options={STANDARDS.map((s) => ({
          value: s,
          label: s === "Dropper" ? "Dropper" : `Class ${s}`,
        }))}
      />
      <ActionSelect
        label="Set stream"
        disabled={pending}
        onPick={onSetStream}
        options={STREAMS.map((s) => ({ value: s, label: s }))}
      />
      <ActionSelect
        label="Assign batch"
        disabled={pending || batches.length === 0}
        onPick={onAssignBatch}
        options={batches.map((b) => ({ value: b.id, label: b.code }))}
      />
      <Button variant="outline" size="sm" onClick={onExport} disabled={pending}>
        Export selected
      </Button>
      <Button
        variant="destructive"
        size="sm"
        onClick={onDelete}
        disabled={pending}
      >
        Delete
      </Button>
      <Button variant="ghost" size="sm" onClick={onClear} disabled={pending}>
        Clear
      </Button>
    </div>
  );
}
