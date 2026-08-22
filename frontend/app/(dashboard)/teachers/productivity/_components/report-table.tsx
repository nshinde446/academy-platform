"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import type { ProductivityReportTeacherRow } from "../_schemas/productivity-report";

type SortKey =
  | "name"
  | "scheduled"
  | "conducted"
  | "completion_pct"
  | "punctuality_pct"
  | "avg_delay_min"
  | "hours"
  | "topics_covered";

function pct(v: number | null): string {
  return v == null ? "—" : `${v}%`;
}

function pctTone(v: number | null, good: number, ok: number) {
  if (v == null) return null;
  if (v >= good) return "success" as const;
  if (v >= ok) return "secondary" as const;
  return "destructive" as const;
}

function sortValue(r: ProductivityReportTeacherRow, key: SortKey): number | string {
  switch (key) {
    case "name":
      return `${r.first_name} ${r.last_name}`.toLowerCase();
    case "completion_pct":
      return r.completion_pct ?? -1;
    case "punctuality_pct":
      return r.punctuality_pct ?? -1;
    case "topics_covered":
      return r.topics_covered;
    default:
      return r[key];
  }
}

export function ReportTable({ rows }: { rows: ProductivityReportTeacherRow[] }) {
  const router = useRouter();
  const [sortKey, setSortKey] = useState<SortKey>("scheduled");
  const [asc, setAsc] = useState(false);

  const sorted = useMemo(() => {
    const copy = [...rows];
    copy.sort((a, b) => {
      const av = sortValue(a, sortKey);
      const bv = sortValue(b, sortKey);
      if (av < bv) return asc ? -1 : 1;
      if (av > bv) return asc ? 1 : -1;
      return 0;
    });
    return copy;
  }, [rows, sortKey, asc]);

  function toggleSort(key: SortKey) {
    if (key === sortKey) {
      setAsc((v) => !v);
    } else {
      setSortKey(key);
      setAsc(key === "name");
    }
  }

  function arrow(key: SortKey) {
    if (key !== sortKey) return "";
    return asc ? " ▲" : " ▼";
  }

  return (
    <div className="rounded-xl border ring-1 ring-foreground/10 overflow-hidden">
      <Table>
        <TableHeader>
          <TableRow>
            <SortHead onClick={() => toggleSort("name")} label={`Teacher${arrow("name")}`} />
            <SortHead
              right
              onClick={() => toggleSort("scheduled")}
              label={`Scheduled${arrow("scheduled")}`}
            />
            <SortHead
              right
              onClick={() => toggleSort("conducted")}
              label={`Conducted${arrow("conducted")}`}
            />
            <SortHead
              right
              onClick={() => toggleSort("completion_pct")}
              label={`Completion${arrow("completion_pct")}`}
            />
            <SortHead
              right
              onClick={() => toggleSort("punctuality_pct")}
              label={`Punctuality${arrow("punctuality_pct")}`}
            />
            <SortHead
              right
              className="hidden md:table-cell"
              onClick={() => toggleSort("avg_delay_min")}
              label={`Avg delay${arrow("avg_delay_min")}`}
            />
            <SortHead
              right
              className="hidden sm:table-cell"
              onClick={() => toggleSort("hours")}
              label={`Hours${arrow("hours")}`}
            />
            <SortHead
              right
              className="hidden lg:table-cell"
              onClick={() => toggleSort("topics_covered")}
              label={`Topics${arrow("topics_covered")}`}
            />
          </TableRow>
        </TableHeader>
        <TableBody>
          {sorted.map((t) => {
            const cTone = pctTone(t.completion_pct, 90, 75);
            const pTone = pctTone(t.punctuality_pct, 85, 70);
            return (
              <TableRow
                key={t.teacher_id}
                className="cursor-pointer"
                onClick={() => router.push(`/teachers/${t.teacher_id}`)}
                title="Open teacher — day-by-day log"
              >
                <TableCell className="font-medium">
                  {t.first_name} {t.last_name}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {t.scheduled}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {t.conducted}
                </TableCell>
                <TableCell className="text-right">
                  {cTone ? (
                    <Badge variant={cTone}>{pct(t.completion_pct)}</Badge>
                  ) : (
                    <span className="text-muted-foreground">—</span>
                  )}
                </TableCell>
                <TableCell className="text-right">
                  {pTone ? (
                    <Badge variant={pTone}>{pct(t.punctuality_pct)}</Badge>
                  ) : (
                    <span className="text-muted-foreground">—</span>
                  )}
                </TableCell>
                <TableCell className="hidden md:table-cell text-right tabular-nums text-muted-foreground">
                  {t.late_count > 0 ? `${t.avg_delay_min}m` : "—"}
                </TableCell>
                <TableCell className="hidden sm:table-cell text-right tabular-nums text-muted-foreground">
                  {t.hours}h
                </TableCell>
                <TableCell className="hidden lg:table-cell text-right tabular-nums text-muted-foreground">
                  {t.topics_covered}/{t.topics_planned}
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}

function SortHead({
  label,
  onClick,
  right,
  className,
}: {
  label: string;
  onClick: () => void;
  right?: boolean;
  className?: string;
}) {
  return (
    <TableHead className={`${right ? "text-right" : ""} ${className ?? ""}`}>
      <button
        type="button"
        onClick={onClick}
        className="font-medium hover:text-foreground"
      >
        {label}
      </button>
    </TableHead>
  );
}
