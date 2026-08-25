import {
  type CableGeo,
  edgeToward,
  intercept,
  type PodGeom,
  type Rect,
} from "@core/canvas/cableGeometry";
import { CANVAS_NODES } from "@core/canvas/canvasNodes";

/**
 * Which cables exist and where their ends land, given geometry measured from
 * the assembled 2.5D hub. Keeping this arithmetic outside React makes the
 * layout rules testable without a browser.
 */
export interface CableScene {
  stage: { width: number; height: number };
  mainPod: PodGeom;
  nodeRects: Partial<Record<string, Rect>>;
  doneKeys: ReadonlySet<string>;
}

export function buildCables(scene: CableScene): CableGeo {
  const cables = [];
  for (const node of CANVAS_NODES) {
    const rect = scene.nodeRects[node.key];
    if (!rect) continue;
    const panel = edgeToward(rect, scene.mainPod.center.x, scene.mainPod.center.y);
    const hit = intercept(scene.mainPod, panel.x, panel.y);
    cables.push({
      id: node.key,
      x1: panel.x,
      y1: panel.y,
      x2: hit.x,
      y2: hit.y,
      stageKey: node.key,
      connected: scene.doneKeys.has(node.key),
    });
  }
  return {
    cables,
    w: scene.stage.width,
    h: scene.stage.height,
    nodeRects: scene.nodeRects,
  };
}
