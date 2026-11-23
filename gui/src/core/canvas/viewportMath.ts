import type { Point } from "./cableGeometry";

export interface Transform {
  x: number;
  y: number;
  z: number;
}

export const ZOOM_MIN = 0.28;
export const ZOOM_MAX = 1.7;
const WHEEL_ZOOM_STEP = 1.1;

export interface StageBox {
  left: number;
  top: number;
  width: number;
  height: number;
}

export interface WorldBounds {
  left: number;
  top: number;
  width: number;
  height: number;
}

export function clampZoom(z: number): number {
  return Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, z));
}

export function fitBounds(
  viewport: Pick<StageBox, "width" | "height">,
  bounds: WorldBounds,
  padding = 24,
): Transform {
  const availableWidth = Math.max(1, viewport.width - padding * 2);
  const availableHeight = Math.max(1, viewport.height - padding * 2);
  const z = clampZoom(Math.min(availableWidth / bounds.width, availableHeight / bounds.height));
  const centreX = bounds.left + bounds.width / 2;
  const centreY = bounds.top + bounds.height / 2;
  return { x: -centreX * z, y: -centreY * z, z };
}

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
