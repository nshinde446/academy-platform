// Google-Sheets-style "Green–White–Red" colour scale for the rank list.
//
// Each marks column is scaled within itself: the column's lowest mark is red,
// the midpoint (the average of the column's min and max) is white, and the
// highest mark is green. Absentees are excluded by the caller, so a blank/zero
// never drags the scale. Mirrors `ranklist_export.py` on the backend so the
// on-screen table, the PDF and the Excel all look the same.

type RGB = [number, number, number];

const RED: RGB = [0xe6, 0x7c, 0x73];
const WHITE: RGB = [0xff, 0xff, 0xff];
const GREEN: RGB = [0x57, 0xbb, 0x8a];

function lerp(a: RGB, b: RGB, t: number): RGB {
  return [
    Math.round(a[0] + (b[0] - a[0]) * t),
    Math.round(a[1] + (b[1] - a[1]) * t),
    Math.round(a[2] + (b[2] - a[2]) * t),
  ];
}

/**
 * Background colour for `value` on the column's own red→white→green scale, or
 * `undefined` when there is nothing to scale (no spread, or no value), so the
 * caller leaves the cell its default background.
 */
export function cellColor(
  value: number | null | undefined,
  min: number,
  max: number,
): string | undefined {
  if (value == null || max <= min) return undefined;
  const mid = (min + max) / 2;
  let rgb: RGB;
  if (value >= mid) {
    const t = max > mid ? (value - mid) / (max - mid) : 0;
    rgb = lerp(WHITE, GREEN, t);
  } else {
    const t = mid > min ? (value - min) / (mid - min) : 1;
    rgb = lerp(RED, WHITE, t);
  }
  return `rgb(${rgb[0]}, ${rgb[1]}, ${rgb[2]})`;
}

/** Min/max of a set of marks, ignoring null/undefined (absent). */
export function columnBounds(
  values: Array<number | null | undefined>,
): { min: number; max: number } | undefined {
  const nums = values.filter((v): v is number => v != null);
  if (nums.length === 0) return undefined;
  return { min: Math.min(...nums), max: Math.max(...nums) };
}
