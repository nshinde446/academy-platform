"use client";

// Renders a string containing $inline$ and $$display$$ LaTeX segments.
// Plain text segments are emitted as-is. KaTeX errors degrade to the
// raw source so the admin can spot bad TeX in the review queue.

import { InlineMath, BlockMath } from "react-katex";
import "katex/dist/katex.min.css";

interface MathTextProps {
  text: string;
  className?: string;
}

type Seg =
  | { kind: "text"; value: string }
  | { kind: "inline"; value: string }
  | { kind: "block"; value: string };

function tokenize(s: string): Seg[] {
  const out: Seg[] = [];
  let i = 0;
  while (i < s.length) {
    if (s.startsWith("$$", i)) {
      const close = s.indexOf("$$", i + 2);
      if (close === -1) {
        out.push({ kind: "text", value: s.slice(i) });
        break;
      }
      out.push({ kind: "block", value: s.slice(i + 2, close) });
      i = close + 2;
      continue;
    }
    if (s[i] === "$") {
      const close = s.indexOf("$", i + 1);
      if (close === -1) {
        out.push({ kind: "text", value: s.slice(i) });
        break;
      }
      out.push({ kind: "inline", value: s.slice(i + 1, close) });
      i = close + 1;
      continue;
    }
    // Plain text run — accumulate up to the next $.
    const next = s.indexOf("$", i);
    if (next === -1) {
      out.push({ kind: "text", value: s.slice(i) });
      break;
    }
    out.push({ kind: "text", value: s.slice(i, next) });
    i = next;
  }
  return out;
}

export function MathText({ text, className }: MathTextProps) {
  if (!text) return null;
  const segs = tokenize(text);
  return (
    <span className={className}>
      {segs.map((seg, idx) => {
        if (seg.kind === "text") return <span key={idx}>{seg.value}</span>;
        if (seg.kind === "inline") {
          try {
            return <InlineMath key={idx} math={seg.value} />;
          } catch {
            return <code key={idx}>${seg.value}$</code>;
          }
        }
        try {
          return <BlockMath key={idx} math={seg.value} />;
        } catch {
          return <code key={idx}>$${seg.value}$$</code>;
        }
      })}
    </span>
  );
}
