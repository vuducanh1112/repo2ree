import type { Point } from "./cableGeometry";

/** Pan (x, y) and zoom (z) of the world layer. */
export interface Transform {
  x: number;
  y: number;
  z: number;
}

// Small screens need to frame the complete 2.5D constellation.
export const ZOOM_MIN = 0.28;
export const ZOOM_MAX = 1.7;
// One wheel notch. Zooming out is the exact inverse, so a notch each way
// returns to where it started.
const WHEEL_ZOOM_STEP = 1.1;

/** The stage box a pointer position is interpreted against. `DOMRect` satisfies this. */
export interface StageBox {
  left: number;
  top: number;
  width: number;
  height: number;
}

/** Axis-aligned bounds in world coordinates. */
export interface WorldBounds {
  left: number;
  top: number;
  width: number;
  height: number;
}

export function clampZoom(z: number): number {
  return Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, z));
}

/** Frame world-space bounds inside a viewport with an even screen-space inset. */
export function fitBounds(
  viewport: Pick<StageBox, "width" | "height">,
  bounds: WorldBounds,
  padding = 24,
): Transform {
  const availableWidth = Math.max(1, viewport.width - padding * 2);
  const availableHeight = Math.max(1, viewport.height - padding * 2);
  const z = clampZoom(Math.min(availableWidth / bounds.width, availableHeight / bounds.height, 1));
  const centreX = bounds.left + bounds.width / 2;
  const centreY = bounds.top + bounds.height / 2;
  return { x: -centreX * z, y: -centreY * z, z };
}

/**
 * Zoom one wheel notch about the pointer, keeping whatever is under the cursor
 * under the cursor. `offset` is the pointer's position relative to the world's
 * current centre; scaling by `z/prev.z - 1` moves the world by exactly the
 * amount the zoom would otherwise have shifted that point.
 *
 * At a zoom limit the clamp makes the ratio 0, so a further notch is a no-op
 * rather than a pan — which is also why the measure loop needs its own timeout:
 * a no-op transform fires no `transitionend`.
 */
export function zoomToward(
  prev: Transform,
  pointer: Point,
  stage: StageBox,
  deltaY: number,
): Transform {
  const ox = pointer.x - stage.left - stage.width / 2 - prev.x;
  const oy = pointer.y - stage.top - stage.height / 2 - prev.y;
  const factor = deltaY < 0 ? WHEEL_ZOOM_STEP : 1 / WHEEL_ZOOM_STEP;
  const z = clampZoom(prev.z * factor);
  const ratio = z / prev.z - 1;
  return { x: prev.x - ox * ratio, y: prev.y - oy * ratio, z };
}
