import type React from "react";
import { bottleneckAxis } from "../../../../../core/review/axes";
import type { EvaluationState } from "../../../../../core/review/EvaluationState";
import { PodSphere } from "./podWidget/PodSphere";
import { POD_M } from "./podWidget/podWidgetData";

interface PodWidgetProps {
  evaluation: EvaluationState;
  svgRef?: React.RefObject<SVGSVGElement>;
  size?: number;
  compact?: boolean;
}
export function PodWidget({ evaluation, svgRef, size = 480, compact = false }: PodWidgetProps) {
  const tint = bottleneckAxis(evaluation).axis.color;
  const W = 580,
    H = 580,
    Cx = 290,
    Cy = 290,
    Sr = 118;
  const shadow = compact
    ? `drop-shadow(0 1px 4px ${tint}20)`
    : `drop-shadow(0 4px 24px ${tint}28) drop-shadow(0 2px 8px ${POD_M.shadow})`;
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
      <PodSphere CX={Cx} CY={Cy} SR={Sr} evaluation={evaluation} />
    </svg>
  );
}
