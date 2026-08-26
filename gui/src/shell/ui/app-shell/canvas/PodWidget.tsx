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
  /** Which of the pod's shells have work running inside them right now. */
  activity?: CanvasActivity;
  /** Unique suffix for SVG IDs when multiple pods are on the same page. */
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
  // The pod's shells are concentric, so every part that moves while a step runs
  // turns about this one centre — declared once on the root below, inherited
  // rather than repeated on each animated element.
  const glowColor = shell === "inner" || shell === "core" ? "var(--pod-glow-mid)" : tint;
  // The glow percentages are the old `${color}25` / `${color}35` hex-alpha
  // suffixes: 0x25 is 14.5% and 0x35 is 20.8%. They are composed rather than
  // appended because `tint` is now a var() reference, and text glued onto one
  // makes an invalid value that fails silently.
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
