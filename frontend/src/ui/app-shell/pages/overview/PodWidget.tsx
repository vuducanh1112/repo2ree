import type React from "react";
import { LEVELS } from "../../../../core/review/levels";
import { PodSphere } from "./podWidget/PodSphere";
import { POD_M } from "./podWidget/podWidgetData";

interface PodWidgetProps {
  level: number;
  svgRef?: React.RefObject<SVGSVGElement>;
  size?: number;
  compact?: boolean;
}
export function PodWidget({ level, svgRef, size = 480, compact = false }: PodWidgetProps) {
  const levelMeta = LEVELS[Math.min(level, 7)];
  const W = 580,
    H = 580,
    Cx = 290,
    Cy = 290,
    Sr = 118;
  const shadow = compact
    ? `drop-shadow(0 1px 4px ${levelMeta.color}20)`
    : `drop-shadow(0 4px 24px ${levelMeta.color}28) drop-shadow(0 2px 8px ${POD_M.shadow})`;
  return (
    <svg
      ref={svgRef}
      width={size}
      height={size}
      viewBox={`0 0 ${W} ${H}`}
      style={{
        flexShrink: 0,
        overflow: "visible",
        filter: shadow,
      }}
    >
      <title>Specimen Pod</title>
      <PodSphere CX={Cx} CY={Cy} SR={Sr} level={level} />
    </svg>
  );
}
