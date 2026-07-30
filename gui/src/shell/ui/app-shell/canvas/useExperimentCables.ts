import { type CableGeo, podGeomFromMatrix, type Rect } from "@core/canvas/cableGeometry";
import {
  buildExperimentCables,
  type CoreCableTarget,
  type ExperimentCableScene,
} from "@core/canvas/cableScene";
import { useCallback, useState } from "react";
import type { NodeOffsets, Transform } from "./useCanvasViewport";
import { useMeasuredCables } from "./useMeasuredCables";

export type { CoreCableTarget };

interface Options {
  stageRef: React.RefObject<HTMLDivElement>;
  coreSvgRef: React.RefObject<SVGSVGElement>;
  worldRef: React.RefObject<HTMLDivElement>;
  satEls: React.MutableRefObject<Record<string, HTMLElement | null>>;
  targets: CoreCableTarget[];
  // tf/nodeOffsets are re-measure triggers, not inputs: measure reads the live
  // DOM transform via getScreenCTM rather than these values.
  tf: Transform;
  nodeOffsets: NodeOffsets;
  animate: boolean;
}

// Measures a cable from each satellite panel to the core pod's surface in the
// stage's screen space (so the world layer's pan/zoom is absorbed), then hands
// the result to the shared cable overlay. A focused twin of the main canvas's
// useCableGeometry: one pod, a flat ring of satellites, no shells or chain —
// and, since both were extracted, the same primitives and the same measure loop.
export function useExperimentCables({
  stageRef,
  coreSvgRef,
  worldRef,
  satEls,
  targets,
  tf,
  nodeOffsets,
  animate,
}: Options): CableGeo | null {
  const [geo, setGeo] = useState<CableGeo | null>(null);

  const measure = useCallback(() => {
    const stage = stageRef.current;
    const coreSvg = coreSvgRef.current;
    if (!stage || !coreSvg) return;
    const cRect = stage.getBoundingClientRect();
    const origin = { x: cRect.left, y: cRect.top };

    const ctm = coreSvg.getScreenCTM();
    if (!ctm) return;

    const satelliteRects: Partial<Record<string, Rect>> = {};
    for (const target of targets) {
      const el = satEls.current[target.key];
      if (!el) continue;
      const r = el.getBoundingClientRect();
      satelliteRects[target.key] = {
        left: r.left - origin.x,
        right: r.right - origin.x,
        top: r.top - origin.y,
        bottom: r.bottom - origin.y,
      };
    }

    const scene: ExperimentCableScene = {
      stage: { width: cRect.width, height: cRect.height },
      corePod: podGeomFromMatrix(ctm, origin),
      targets,
      satelliteRects,
    };
    setGeo(buildExperimentCables(scene));
  }, [stageRef, coreSvgRef, satEls, targets]);

  useMeasuredCables(measure, { stageRef, worldRef, tf, nodeOffsets, animate });

  return geo;
}
