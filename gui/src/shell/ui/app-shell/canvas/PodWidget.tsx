import { type CanvasActivity, NO_CANVAS_ACTIVITY } from "@core/canvas/canvasActivity";
import { bottleneckAxis } from "@core/evaluate/axes";
import type { EvaluationState } from "@core/evaluate/EvaluationState";
import type React from "react";
import { axisTone, translucent } from "../../theme/appearance";
import { cssVars } from "../../theme/styleVars";
import styles from "./PodWidget.module.css";
import { type PodShell, PodSphere } from "./podWidget/PodSphere";
import { POD_M } from "./podWidget/podWidgetData";

interface PodWidgetProps {
  evaluation: EvaluationState;
  svgRef?: React.RefObject<SVGSVGElement>;
  size?: number;
  compact?: boolean;
  shell?: PodShell;
  activity?: CanvasActivity;
  idSuffix?: string;
}
export function PodWidget({
  evaluation,
  svgRef,
  size = 480,
  compact = false,
  shell = "full",
  activity = NO_CANVAS_ACTIVITY,
  idSuffix = "",
}: PodWidgetProps) {
  const tint = axisTone(bottleneckAxis(evaluation).axis.key);
  const W = 580,
    H = 580,
    Cx = 290,
    Cy = 290,
    Sr = 118;
  const glowColor = shell === "inner" || shell === "core" ? "var(--pod-glow-mid)" : tint;
  const shadow = compact
    ? `drop-shadow(0 1px 4px ${translucent(glowColor, 14.5)})`
    : `drop-shadow(0 4px 24px ${translucent(glowColor, 20.8)}) drop-shadow(0 2px 8px ${POD_M.shadow})`;

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
      className={styles.pod}
      style={cssVars({ "--pod-glow": shadow, "--pod-pivot": `${Cx}px ${Cy}px` })}
    >
      <title>{title}</title>
      <PodSphere
        CX={Cx}
        CY={Cy}
        SR={Sr}
        evaluation={evaluation}
        shell={shell}
        activity={activity}
        idSuffix={idSuffix}
      />
    </svg>
  );
}
