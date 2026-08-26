import { type CanvasActivity, NO_CANVAS_ACTIVITY } from "@core/canvas/canvasActivity";
import type { EvaluationState } from "@core/evaluate/EvaluationState";
import type React from "react";
import { cssVars } from "../../theme/styleVars";
import { PodWidget } from "./PodWidget";
import styles from "./SpecimenPod.module.css";

const POD_SIZE = 760;
const POD_BASE_HEIGHT = 44;

export function SpecimenPod({
  evaluation,
  svgRef,
  activity = NO_CANVAS_ACTIVITY,
}: {
  evaluation: EvaluationState;
  svgRef: React.RefObject<SVGSVGElement>;
  /** The shells with work running inside them, so the pod shows it working. */
  activity?: CanvasActivity;
}) {
  // PodWidget's visible sphere has radius 118 inside its 580-unit viewBox.
  // Add the plinth height so the sphere is raised above the bench surface.
  const floorLift = (POD_SIZE * 118) / 580 + POD_BASE_HEIGHT;

  return (
    <div className={styles.specimen}>
      <div className={styles.billboard}>
        <div
          aria-hidden
          className={styles.base}
          style={cssVars({ "--pod-base-height": `${POD_BASE_HEIGHT}px` })}
        />
        <div
          className={styles.graphic}
          style={cssVars({
            "--pod-floor-lift": `${floorLift}px`,
            "--pod-size": `${POD_SIZE}px`,
          })}
        >
          <PodWidget
            evaluation={evaluation}
            svgRef={svgRef}
            activity={activity}
            size={POD_SIZE}
            shell="full"
            idSuffix="outer"
          />
        </div>
      </div>
    </div>
  );
}
