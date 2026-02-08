"use client";

import { useMemo } from "react";

interface Props {
  data: number[];
  width?: number;
  height?: number;
  color?: string;
}

export function Sparkline({ data, width = 80, height = 28, color }: Props) {
  const { path, fillPath, lineColor } = useMemo(() => {
    if (!data.length) return { path: "", fillPath: "", lineColor: "var(--text-5)" };

    const min = Math.min(...data);
    const max = Math.max(...data);
    const range = max - min || 1;
    const padding = 2;
    const w = width - padding * 2;
    const h = height - padding * 2;

    const points = data.map((v, i) => ({
      x: padding + (i / (data.length - 1)) * w,
      y: padding + h - ((v - min) / range) * h,
    }));

    // Smooth SVG path
    let d = `M${points[0].x},${points[0].y}`;
    for (let i = 1; i < points.length; i++) {
      const prev = points[i - 1];
      const curr = points[i];
      const cpx = (prev.x + curr.x) / 2;
      d += ` C${cpx},${prev.y} ${cpx},${curr.y} ${curr.x},${curr.y}`;
    }

    // Fill path (closed at bottom)
    const last = points[points.length - 1];
    const fillD = `${d} L${last.x},${height} L${points[0].x},${height} Z`;

    const isUp = data[data.length - 1] >= data[0];
    return {
      path: d,
      fillPath: fillD,
      lineColor: color || (isUp ? "var(--green)" : "var(--red)"),
    };
  }, [data, width, height, color]);

  if (!data.length) return null;

  return (
    <svg width={width} height={height} className="block">
      <defs>
        <linearGradient id={`spark-${data.length}-${data[0]}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={lineColor} stopOpacity={0.15} />
          <stop offset="100%" stopColor={lineColor} stopOpacity={0} />
        </linearGradient>
      </defs>
      <path
        d={fillPath}
        fill={`url(#spark-${data.length}-${data[0]})`}
      />
      <path
        d={path}
        fill="none"
        stroke={lineColor}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
