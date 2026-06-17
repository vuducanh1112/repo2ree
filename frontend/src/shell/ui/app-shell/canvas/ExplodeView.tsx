import type React from "react";
import type { EvaluationState } from "../../../../core/review/EvaluationState";
import { Ic } from "../../shared/components/Icon";
import { C, F } from "../../theme/theme";
import { PodWidget } from "../pages/overview/PodWidget";
import type { PodShell } from "../pages/overview/podWidget/PodSphere";
import { EXPLODE_BASE_POD, EXPLODE_LAYERS } from "./canvasNodes";

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
}: {
  evaluation: EvaluationState;
  svgRef: React.RefObject<SVGSVGElement>;
  layer: (typeof EXPLODE_LAYERS)[number];
  exploded?: boolean;
}) {
  const isMain = layer.zone === "outer";
  // Assembled: always show the full three-layer pod. Decomposed: each column shows its layer.
  const shell: PodShell = exploded ? (ZONE_SHELL[layer.zone] ?? "full") : "full";
  return (
    <div
      style={{
        position: "absolute",
        left: layer.cx,
        top: 0,
        transform: "translate(-50%,-50%)",
        opacity: isMain || exploded ? 1 : 0,
        transition: "opacity 0.4s",
        pointerEvents: "none",
      }}
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
    <div
      aria-hidden
      style={{
        position: "absolute",
        left: 0,
        top: 0,
        opacity: exploded ? 1 : 0,
        transition: "opacity 0.5s",
        pointerEvents: "none",
      }}
    >
      <div
        style={{
          position: "absolute",
          left: 0,
          top: 0,
          width: EXPLODE_LAYERS[EXPLODE_LAYERS.length - 1].cx,
          borderTop: `2px dashed ${C.accent}`,
          opacity: 0.35,
        }}
      />
      {EXPLODE_LAYERS.map((layer) => (
        <div
          key={layer.zone}
          style={{
            position: "absolute",
            left: layer.cx,
            top: -(EXPLODE_BASE_POD * layer.scale) / 2 - 54,
            width: 260,
            transform: "translateX(-50%)",
            textAlign: "center",
          }}
        >
          <div style={{ fontSize: 21, fontWeight: 700, color: C.text, letterSpacing: -0.3 }}>
            {layer.label}
          </div>
          <div
            style={{
              fontFamily: F.mono,
              fontSize: 11.5,
              letterSpacing: 0.6,
              color: C.textMuted,
              textTransform: "uppercase",
            }}
          >
            {layer.sub}
          </div>
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
      style={{
        position: "absolute",
        top: 14,
        right: 16,
        display: "flex",
        alignItems: "center",
        gap: 7,
        padding: "7px 12px",
        background: exploded ? C.accent : C.surface,
        color: exploded ? "#fff" : C.textMid,
        border: `1px solid ${exploded ? C.accent : C.border}`,
        borderRadius: 9,
        cursor: "pointer",
        fontSize: 12.5,
        fontWeight: 600,
        fontFamily: F.sans,
        boxShadow: "0 4px 14px rgba(13,17,23,0.1)",
      }}
    >
      <span style={{ display: "flex" }}>{Ic.layers(14)}</span>
      {exploded ? "Reassemble" : "Decompose"}
    </button>
  );
}
