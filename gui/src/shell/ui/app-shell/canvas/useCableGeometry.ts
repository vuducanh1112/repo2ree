import {
  type CableGeo,
  type PodGeom,
  podGeomFromMatrix,
  type Rect,
} from "@core/canvas/cableGeometry";
import { buildCables, type CableScene } from "@core/canvas/cableScene";
import { CANVAS_NODES, isNodeDone, type NodeZone } from "@core/canvas/canvasNodes";
import type { Badges } from "@core/ree/ReeTypes";
import type { ReeEditorViewModel } from "@core/ree-editor/reeEditorViewModel";
import { useCallback, useState } from "react";
import type { NodeOffsets, Transform } from "./useCanvasViewport";
import { useMeasuredCables } from "./useMeasuredCables";

interface CableGeometryOptions {
  stageRef: React.RefObject<HTMLDivElement>;
  podSvgRef: React.RefObject<SVGSVGElement>;
  worldRef: React.RefObject<HTMLDivElement>;
  nodeEls: React.MutableRefObject<Record<string, HTMLButtonElement | null>>;
  ree: ReeEditorViewModel;
  badges: Badges;
  // `tf` and `nodeOffsets` are re-measure triggers, not inputs: measure reads the
  // resulting DOM transform via getScreenCTM rather than these values directly.
  tf: Transform;
  nodeOffsets: NodeOffsets;
  animate: boolean;
  /** When true, each shell's cables anchor to its own decomposed column pod. */
  exploded: boolean;
  /** Projection pod elements (inner/core columns) the cables anchor to when exploded. */
  projectionPods: Partial<Record<NodeZone, React.RefObject<SVGSVGElement>>>;
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
  ree,
  badges,
  tf,
  nodeOffsets,
  animate,
  exploded,
  projectionPods,
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

    const measuredPods: Partial<Record<NodeZone, PodGeom>> = {};
    for (const zone of ["inner", "core"] as const) {
      const pod = podOf(projectionPods[zone]?.current ?? null);
      if (pod) measuredPods[zone] = pod;
    }

    const nodeRects: Partial<Record<string, Rect>> = {};
    const doneKeys = new Set<string>();
    for (const node of CANVAS_NODES) {
      const el = nodeEls.current[node.key];
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
      projectionPods: measuredPods,
      nodeRects,
      doneKeys,
      exploded,
    };
    setGeo(buildCables(scene));
  }, [stageRef, podSvgRef, nodeEls, ree, badges, exploded, projectionPods]);

  useMeasuredCables(measure, { stageRef, worldRef, tf, nodeOffsets, animate });

  return geo;
}
