import { bottleneckAxis } from "@core/evaluate/axes";
import type { EvaluationState } from "@core/evaluate/EvaluationState";
import type React from "react";
import { type PodShell, PodSphere } from "./podWidget/PodSphere";
import { POD_M } from "./podWidget/podWidgetData";

interface PodWidgetProps {
  evaluation: EvaluationState;
  svgRef?: React.RefObject<SVGSVGElement>;
  size?: number;
  compact?: boolean;
  shell?: PodShell;
  /** Unique suffix for SVG IDs when multiple pods are on the same page. */
  idSuffix?: string;
}
export function PodWidget({
  evaluation,
  svgRef,
  size = 480,
  compact = false,
  shell = "full",
  idSuffix = "",
}: PodWidgetProps) {
  const tint = bottleneckAxis(evaluation).axis.color;
  const W = 580,
    H = 580,
    Cx = 290,
    Cy = 290,
    Sr = 118;

  const glowColor = shell === "inner" || shell === "core" ? "#38bdf8" : tint;
  const shadow = compact
    ? `drop-shadow(0 1px 4px ${glowColor}25)`
    : `drop-shadow(0 4px 24px ${glowColor}35) drop-shadow(0 2px 8px ${POD_M.shadow})`;

  const title =
    shell === "outer"
      ? "Outer Shell"
      : shell === "inner"
        ? "Inner Shell"
        : shell === "core"
          ? "Core"
          : "Specimen Pod";

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
      <title>{title}</title>
      <PodSphere
        CX={Cx}
        CY={Cy}
        SR={Sr}
        evaluation={evaluation}
        shell={shell}
        idSuffix={idSuffix}
      />
    </svg>
  );
}
