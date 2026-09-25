"use client";

import { useId } from "react";
import { Card, CardContent } from "@/components/ui/card";

export interface PieSlice {
  label: string;
  value: number;
}

// Categorical palette — distinct hues that hold up in light and dark. Extra
// slices cycle; a long tail is folded into "Others" by the caller.
const COLORS = [
  "#4e79a7", "#f28e2b", "#59a14f", "#e15759", "#b07aa1",
  "#76b7b2", "#edc948", "#ff9da7", "#9c755f", "#bab0ac",
];

function polar(cx: number, cy: number, r: number, angle: number): [number, number] {
  const a = (angle - 90) * (Math.PI / 180);
  return [cx + r * Math.cos(a), cy + r * Math.sin(a)];
}

function arcPath(cx: number, cy: number, r: number, from: number, to: number): string {
  // Full circle can't be drawn with a single arc — caller handles the 1-slice case.
  const [sx, sy] = polar(cx, cy, r, to);
  const [ex, ey] = polar(cx, cy, r, from);
  const large = to - from > 180 ? 1 : 0;
  return `M ${cx} ${cy} L ${sx} ${sy} A ${r} ${r} 0 ${large} 0 ${ex} ${ey} Z`;
}

/**
 * A labelled pie chart with a legend showing each slice's count and percent.
 * Empty / all-zero data renders an explanatory note instead of an empty circle.
 */
export function PieChart({
  title,
  slices,
  action,
}: {
  title: string;
  slices: PieSlice[];
  action?: React.ReactNode;
}) {
  const titleId = useId();
  const total = slices.reduce((s, x) => s + x.value, 0);
  const cx = 90;
  const cy = 90;
  const r = 80;

  // Running fraction offset per slice, computed without mutation during render.
  const offsets = slices.reduce<number[]>(
    (acc, s) => [...acc, acc[acc.length - 1]! + s.value / total],
    [0],
  );
  const arcs = slices.map((s, i) => {
    const frac = s.value / total;
    return {
      ...s,
      color: COLORS[i % COLORS.length],
      from: offsets[i]! * 360,
      to: offsets[i + 1]! * 360,
      frac,
    };
  });

  return (
    <Card size="sm">
      <CardContent>
        <div className="mb-3 flex items-center justify-between gap-2">
          <h3 className="text-sm font-semibold" id={titleId}>
            {title}
          </h3>
          {action}
        </div>

        {total <= 0 ? (
          <p className="py-8 text-center text-sm text-muted-foreground">
            No lectures in this range.
          </p>
        ) : (
          <div className="flex flex-wrap items-center gap-4">
            <svg
              viewBox="0 0 180 180"
              width={160}
              height={160}
              role="img"
              aria-labelledby={titleId}
              className="shrink-0"
            >
              {arcs.length === 1 ? (
                <circle cx={cx} cy={cy} r={r} fill={arcs[0].color} />
              ) : (
                arcs.map((a) => (
                  <path
                    key={a.label}
                    d={arcPath(cx, cy, r, a.from, a.to)}
                    fill={a.color}
                  >
                    <title>{`${a.label}: ${a.value} (${Math.round(a.frac * 100)}%)`}</title>
                  </path>
                ))
              )}
            </svg>

            <ul className="flex min-w-[140px] flex-1 flex-col gap-1 text-xs">
              {arcs.map((a) => (
                <li key={a.label} className="flex items-center gap-2">
                  <span
                    aria-hidden
                    className="h-2.5 w-2.5 shrink-0 rounded-sm"
                    style={{ backgroundColor: a.color }}
                  />
                  <span className="flex-1 truncate" title={a.label}>
                    {a.label}
                  </span>
                  <span className="tabular-nums text-muted-foreground">
                    {a.value} · {Math.round(a.frac * 100)}%
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

/** Fold a long tail of slices into a single "Others" slice, keeping top N. */
export function withOthers(slices: PieSlice[], topN = 9): PieSlice[] {
  const sorted = [...slices].filter((s) => s.value > 0).sort((a, b) => b.value - a.value);
  if (sorted.length <= topN) return sorted;
  const head = sorted.slice(0, topN);
  const rest = sorted.slice(topN).reduce((s, x) => s + x.value, 0);
  return rest > 0 ? [...head, { label: "Others", value: rest }] : head;
}
