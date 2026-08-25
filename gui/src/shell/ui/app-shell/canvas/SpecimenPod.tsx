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
}: {
  evaluation: EvaluationState;
  svgRef: React.RefObject<SVGSVGElement>;
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
            size={POD_SIZE}
            shell="full"
            idSuffix="outer"
          />
        </div>
      </div>
    </div>
  );
}
