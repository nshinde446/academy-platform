"use client";

import { useMemo } from "react";
import { Input } from "@/components/ui/input";

/**
 * A less-tedious datetime picker: a native date input paired with a *typeable*
 * time dropdown on a fixed-step grid (e.g. every 15 min) — instead of the native
 * `datetime-local` minute spinner that forces endless scrolling.
 *
 * Value is the `datetime-local` string "YYYY-MM-DDTHH:mm" (same shape the
 * lecture dialogs already use), so it's a drop-in replacement. An off-grid time
 * (e.g. a seeded 10:07 actual) is preserved as an extra option so nothing is
 * silently rounded.
 */

function splitValue(v: string): { date: string; time: string } {
  if (!v || !v.includes("T")) return { date: v || "", time: "" };
  const [d, t] = v.split("T");
  return { date: d, time: (t || "").slice(0, 5) };
}

function to12h(hhmm: string): string {
  const [h, m] = hhmm.split(":").map(Number);
  if (Number.isNaN(h)) return hhmm;
  const ap = h < 12 ? "AM" : "PM";
  const h12 = ((h + 11) % 12) + 1;
  return `${h12}:${String(m).padStart(2, "0")} ${ap}`;
}

function buildOptions(
  step: number,
  minHour: number,
  maxHour: number,
  current: string,
): string[] {
  const opts: string[] = [];
  for (let mins = minHour * 60; mins <= maxHour * 60; mins += step) {
    const hh = String(Math.floor(mins / 60)).padStart(2, "0");
    const mm = String(mins % 60).padStart(2, "0");
    opts.push(`${hh}:${mm}`);
  }
  // Keep any already-set time that isn't on the grid (e.g. a recorded 10:07).
  if (current && !opts.includes(current)) {
    opts.push(current);
    opts.sort();
  }
  return opts;
}

/** Add minutes to a "YYYY-MM-DDTHH:mm" local string, returning the same shape. */
export function addMinutesToLocal(local: string, minutes: number): string {
  const d = new Date(local);
  if (Number.isNaN(d.getTime())) return local;
  d.setMinutes(d.getMinutes() + minutes);
  const shifted = new Date(d.getTime() - d.getTimezoneOffset() * 60_000);
  return shifted.toISOString().slice(0, 16);
}

interface DateTimeFieldProps {
  /** Applied to the date input so an external <Label htmlFor> associates with it. */
  id?: string;
  value: string;
  onChange: (next: string) => void;
  /** Time-grid granularity in minutes (default 15). */
  step?: number;
  /** Time-of-day window shown in the dropdown (24h). Default 6:00–22:00. */
  minHour?: number;
  maxHour?: number;
  disabled?: boolean;
  required?: boolean;
  /** Accessible name base; the time <select> gets "<ariaLabel> time". */
  ariaLabel?: string;
}

export function DateTimeField({
  id,
  value,
  onChange,
  step = 15,
  minHour = 6,
  maxHour = 22,
  disabled,
  required,
  ariaLabel,
}: DateTimeFieldProps) {
  const { date, time } = splitValue(value);
  const options = useMemo(
    () => buildOptions(step, minHour, maxHour, time),
    [step, minHour, maxHour, time],
  );

  function emit(nextDate: string, nextTime: string) {
    if (!nextDate && !nextTime) {
      onChange("");
      return;
    }
    onChange(`${nextDate}T${nextTime || "00:00"}`);
  }

  return (
    <div className="flex gap-2">
      <Input
        id={id}
        type="date"
        value={date}
        disabled={disabled}
        required={required}
        aria-label={ariaLabel ? `${ariaLabel} date` : undefined}
        className="flex-1"
        onChange={(e) => emit(e.target.value, time)}
      />
      <select
        value={time}
        disabled={disabled}
        required={required}
        aria-label={ariaLabel ? `${ariaLabel} time` : undefined}
        className="h-9 shrink-0 rounded-lg border border-input bg-background px-2 text-sm"
        onChange={(e) => emit(date, e.target.value)}
      >
        <option value="">--:--</option>
        {options.map((o) => (
          <option key={o} value={o}>
            {to12h(o)}
          </option>
        ))}
      </select>
    </div>
  );
}
