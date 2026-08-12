import { EXPLODE_BASE_POD, EXPLODE_LAYERS } from "@core/canvas/canvasNodes";
import type { EvaluationState } from "@core/evaluate/EvaluationState";
import type React from "react";
import { Ic } from "../../shared/components/Icon";
import { cssVars } from "../../theme/styleVars";
import styles from "./ExplodeView.module.css";
import { PodWidget } from "./PodWidget";
import type { PodShell } from "./podWidget/PodSphere";

// Zone → isolated shell for the decomposed view.
const ZONE_SHELL: Record<string, PodShell> = {
  outer: "outer",
  inner: "inner",
  core: "core",
};

// One pod graphic per column: the full specimen at origin, then shrinking
// projections to the right. Each carries an svgRef so the cable geometry can
// anchor that shell's cables to the real pod surface.
export function ProjectionPod({
  evaluation,
  svgRef,
  layer,
  exploded = true,
  glow = false,
}: {
  evaluation: EvaluationState;
  svgRef: React.RefObject<SVGSVGElement>;
  layer: (typeof EXPLODE_LAYERS)[number];
  exploded?: boolean;
  /** Make the pod itself shine — used as the core's clickable hover cue. */
  glow?: boolean;
}) {
  const isMain = layer.zone === "outer";
  // Assembled: always show the full three-layer pod. Decomposed: each column shows its layer.
  const shell: PodShell = exploded ? (ZONE_SHELL[layer.zone] ?? "full") : "full";
  return (
    <div
      className={styles.column}
      data-visible={isMain || exploded ? true : undefined}
      data-glow={glow || undefined}
      style={cssVars({ "--column-x": `${layer.cx}px` })}
    >
      <PodWidget
        evaluation={evaluation}
        svgRef={svgRef}
        size={EXPLODE_BASE_POD * layer.scale}
        compact={!isMain}
        shell={shell}
        idSuffix={layer.zone}
      />
    </div>
  );
}

// The projection axis and per-column captions for the decomposed view. Lives
// inside the world transform so it pans/zooms with everything else.
export function ExplodeScaffold({ exploded }: { exploded: boolean }) {
  return (
    <div aria-hidden className={styles.labels} data-visible={exploded || undefined}>
      <div
        className={styles.axis}
        style={cssVars({
          "--axis-width": `${EXPLODE_LAYERS[EXPLODE_LAYERS.length - 1].cx}px`,
        })}
      />
      {EXPLODE_LAYERS.map((layer) => (
        <div
          key={layer.zone}
          className={styles.caption}
          style={cssVars({
            "--column-x": `${layer.cx}px`,
            "--caption-y": `${-(EXPLODE_BASE_POD * layer.scale) / 2 - 54}px`,
          })}
        >
          <div className={styles.captionTitle}>{layer.label}</div>
          <div className={styles.captionSub}>{layer.sub}</div>
        </div>
      ))}
    </div>
  );
}

export function ExplodeToggle({ exploded, onToggle }: { exploded: boolean; onToggle: () => void }) {
  return (
    <button
      type="button"
      data-canvas-hud
      onClick={onToggle}
      title={exploded ? "Reassemble the pod" : "Decompose the pod into its shells"}
      aria-pressed={exploded}
      className={styles.toggle}
    >
      <span aria-hidden className={styles.toggleIcon}>
        {Ic.layers(14)}
      </span>
      {exploded ? "Reassemble" : "Decompose"}
    </button>
  );
}
