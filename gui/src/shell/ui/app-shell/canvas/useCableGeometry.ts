import {
  type CableGeo,
  type PodGeom,
  podGeomFromMatrix,
  type Rect,
} from "@core/canvas/cableGeometry";
import { buildCables, type CableScene } from "@core/canvas/cableScene";
import { CANVAS_NODES, isNodeDone } from "@core/canvas/canvasNodes";
import type { Badges } from "@core/ree/ReeTypes";
import type { ReeEditorViewModel } from "@core/ree-editor/reeEditorViewModel";
import { useCallback, useState } from "react";
import type { Transform } from "./useCanvasViewport";
import { useMeasuredCables } from "./useMeasuredCables";

interface CableGeometryOptions {
  stageRef: React.RefObject<HTMLDivElement>;
  podSvgRef: React.RefObject<SVGSVGElement>;
  worldRef: React.RefObject<HTMLDivElement>;
  nodeEls: React.MutableRefObject<Record<string, HTMLButtonElement | null>>;
  nodePortEls: React.MutableRefObject<Record<string, HTMLSpanElement | null>>;
  ree: ReeEditorViewModel;
  badges: Badges;
  // `tf` is a re-measure trigger, not an input: measure reads the
  // resulting DOM transform via getScreenCTM rather than these values directly.
  tf: Transform;
  animate: boolean;
}

// Measures cable endpoints between each node card and the pod's surface in the
// stage's screen space (so the world layer's pan/zoom transform is absorbed),
// then feeds the shared Overview cable look.
//
// This hook only reads the DOM. Which cables exist, and where their ends land,
// is `buildCables` in cableScene.ts — so the layout rules are testable without
// a browser and only the three measurements below need one.
export function useCableGeometry({
  stageRef,
  podSvgRef,
  worldRef,
  nodeEls,
  nodePortEls,
  ree,
  badges,
  tf,
  animate,
}: CableGeometryOptions): CableGeo | null {
  const [geo, setGeo] = useState<CableGeo | null>(null);

  const measure = useCallback(() => {
    const stage = stageRef.current;
    const podSvg = podSvgRef.current;
    if (!stage || !podSvg) return;
    const cRect = stage.getBoundingClientRect();
    const origin = { x: cRect.left, y: cRect.top };

    const podOf = (svg: SVGSVGElement | null): PodGeom | undefined => {
      const ctm = svg?.getScreenCTM();
      return ctm ? podGeomFromMatrix(ctm, origin) : undefined;
    };

    const mainPod = podOf(podSvg);
    if (!mainPod) return;

    const nodeRects: Partial<Record<string, Rect>> = {};
    const doneKeys = new Set<string>();
    for (const node of CANVAS_NODES) {
      // Prefer the card's explicit connector. Falling back to the card keeps
      // the geometry resilient while refs settle during a layout transition.
      const el = nodePortEls.current[node.key] ?? nodeEls.current[node.key];
      if (el) {
        const r = el.getBoundingClientRect();
        nodeRects[node.key] = {
          left: r.left - origin.x,
          right: r.right - origin.x,
          top: r.top - origin.y,
          bottom: r.bottom - origin.y,
        };
      }
      if (isNodeDone(node, ree, badges)) doneKeys.add(node.key);
    }

    const scene: CableScene = {
      stage: { width: cRect.width, height: cRect.height },
      mainPod,
      nodeRects,
      doneKeys,
    };
    setGeo(buildCables(scene));
  }, [stageRef, podSvgRef, nodeEls, nodePortEls, ree, badges]);

  useMeasuredCables(measure, { stageRef, worldRef, tf, animate });

  return geo;
}
