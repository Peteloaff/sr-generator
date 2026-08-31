"use client";

import { useMemo } from "react";
import type { Section } from "@/lib/api";

const SECTION_COLORS: Record<string, string> = {
  intro: "#3b82f6", verse: "#22c55e", pre_chorus: "#eab308", chorus: "#f97316",
  post_chorus: "#a855f7", bridge: "#06b6d4", breakdown: "#ef4444", solo: "#ec4899",
  outro: "#64748b", other: "#94a3b8",
};

export function sectionColor(t: string) {
  return SECTION_COLORS[t] ?? SECTION_COLORS.other;
}

export default function Waveform({
  peaks,
  duration,
  sections = [],
  onSeek,
}: {
  peaks: number[][];
  duration: number | null;
  sections?: Section[];
  onSeek?: (seconds: number) => void;
}) {
  const W = 1000;
  const H = 140;
  const path = useMemo(() => {
    if (!peaks.length) return "";
    const step = W / peaks.length;
    const mid = H / 2;
    let d = "";
    peaks.forEach(([lo, hi], i) => {
      const x = i * step;
      d += `M${x.toFixed(2)},${(mid - hi * mid).toFixed(2)} L${x.toFixed(2)},${(mid - lo * mid).toFixed(2)} `;
    });
    return d;
  }, [peaks]);

  const dur = duration ?? 0;

  return (
    <svg
      className="waveform"
      viewBox={`0 0 ${W} ${H}`}
      preserveAspectRatio="none"
      onClick={(e) => {
        if (!onSeek || !dur) return;
        const rect = (e.target as SVGElement).closest("svg")!.getBoundingClientRect();
        onSeek(((e.clientX - rect.left) / rect.width) * dur);
      }}
    >
      {dur > 0 &&
        sections.map((s) => {
          const x0 = ((s.start_time ?? 0) / dur) * W;
          const x1 = ((s.end_time ?? s.start_time ?? 0) / dur) * W;
          if (x1 <= x0) return null;
          return (
            <rect
              key={s.id}
              x={x0}
              y={0}
              width={x1 - x0}
              height={H}
              fill={sectionColor(s.section_type)}
              opacity={0.16}
            />
          );
        })}
      <path d={path} stroke="var(--accent)" strokeWidth={1} fill="none" />
      <line x1={0} y1={H / 2} x2={W} y2={H / 2} stroke="var(--line)" strokeWidth={0.5} />
    </svg>
  );
}
