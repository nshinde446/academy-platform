"use client";

import { PAPER_TYPE_LABEL, type TestResponse } from "../_schemas/paper";
import type { PdfKind } from "../_hooks/use-papers";

interface RecentPapersProps {
  papers: TestResponse[];
  onDownload: (paper: TestResponse, kind: PdfKind) => void;
  busyKey: string | null;
}

export function RecentPapers({ papers, onDownload, busyKey }: RecentPapersProps) {
  if (papers.length === 0) return null;

  return (
    <div className="rounded-xl border bg-card p-4">
      <h3 className="mb-2 text-sm font-medium">Recent papers</h3>
      <ul className="flex flex-col divide-y">
        {papers.map((p) => (
          <li key={p.id} className="flex items-center gap-3 py-2 text-sm">
            <span className="rounded border border-border px-1.5 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
              {PAPER_TYPE_LABEL[p.paper_type]}
            </span>
            <span className="min-w-0 flex-1 truncate">{p.name}</span>
            <span className="text-[11px] uppercase tracking-wide text-muted-foreground">
              {p.test_status}
            </span>
            <button
              type="button"
              onClick={() => onDownload(p, "paper")}
              disabled={busyKey === `${p.id}:paper`}
              className="rounded border px-2 py-0.5 text-[11px] transition-colors hover:bg-muted disabled:opacity-50"
            >
              {busyKey === `${p.id}:paper` ? "…" : "Paper"}
            </button>
            <button
              type="button"
              onClick={() => onDownload(p, "answer-key")}
              disabled={busyKey === `${p.id}:answer-key`}
              className="rounded border px-2 py-0.5 text-[11px] transition-colors hover:bg-muted disabled:opacity-50"
            >
              {busyKey === `${p.id}:answer-key` ? "…" : "Key"}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
