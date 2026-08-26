import { describe, expect, it } from "vitest";
import type { Rect } from "./cableGeometry";
import {
  cascadeClear,
  MIN_WINDOW_SIZE,
  placeNodeWindow,
  resizeWindowFromEdge,
} from "./nodeWindowPlacement";

const STAGE = { width: 1600, height: 900 };
const SIZE = { width: 700, height: 540 };

function rect(left: number, top: number, width = 180, height = 90): Rect {
  return { left, top, right: left + width, bottom: top + height };
}

describe("placeNodeWindow", () => {
  it("opens on the node's outward side, away from the pod at the centre", () => {
    // Room enough on the outward side of each: left node goes left, right goes right.
    expect(placeNodeWindow(rect(760, 400), STAGE, SIZE).x).toBe(760 - 20 - 700);
    expect(placeNodeWindow(rect(660, 400), STAGE, SIZE).x).toBe(660 + 180 + 20);
  });

  it("falls back to the inward side when the outward one does not fit", () => {
    // Outward (left) would land at -220, so it opens inward instead.
    expect(placeNodeWindow(rect(500, 400), STAGE, SIZE).x).toBe(500 + 180 + 20);
  });

  it("centres the window on its node vertically", () => {
    const node = rect(900, 400);
    expect(placeNodeWindow(node, STAGE, SIZE).y).toBe(400 + 45 - 270);
  });

  it("keeps a window opened from an edge node fully on the stage", () => {
    for (const node of [rect(0, 0), rect(1420, 810), rect(0, 810), rect(1420, 0)]) {
      const { x, y } = placeNodeWindow(node, STAGE, SIZE);
      expect(x).toBeGreaterThanOrEqual(12);
      expect(y).toBeGreaterThanOrEqual(12);
      expect(x + SIZE.width).toBeLessThanOrEqual(STAGE.width - 12);
      expect(y + SIZE.height).toBeLessThanOrEqual(STAGE.height - 12);
    }
  });

  it("pins a window too large for its stage rather than centring it out of reach", () => {
    const tiny = { width: 400, height: 300 };
    const { x, y } = placeNodeWindow(rect(100, 100), tiny, SIZE);
    // The title bar and its close button stay on screen.
    expect(x).toBe(12);
    expect(y).toBe(12);
  });
});

describe("resizeWindowFromEdge", () => {
  const geometry = { position: { x: 300, y: 160 }, size: SIZE };

  it("resizes from the southeast without moving the origin", () => {
    expect(resizeWindowFromEdge(geometry, "se", { x: 80, y: 40 }, STAGE)).toEqual({
      position: { x: 300, y: 160 },
      size: { width: 780, height: 580 },
    });
  });

  it("resizes from the northwest and moves the origin", () => {
    expect(resizeWindowFromEdge(geometry, "nw", { x: 50, y: 30 }, STAGE)).toEqual({
      position: { x: 350, y: 190 },
      size: { width: 650, height: 510 },
    });
  });

  it("enforces the minimum size from the west edge", () => {
    expect(resizeWindowFromEdge(geometry, "w", { x: 1000, y: 0 }, STAGE)).toEqual({
      position: { x: 580, y: 160 },
      size: { width: MIN_WINDOW_SIZE.width, height: SIZE.height },
    });
  });

  it("keeps resized edges inside the stage", () => {
    expect(resizeWindowFromEdge(geometry, "nw", { x: -1000, y: -1000 }, STAGE)).toEqual({
      position: { x: 12, y: 12 },
      size: { width: 988, height: 688 },
    });
  });

  it("clamps southeast growth to the available stage", () => {
    expect(resizeWindowFromEdge(geometry, "se", { x: 2000, y: 2000 }, STAGE)).toEqual({
      position: geometry.position,
      size: { width: 1288, height: 728 },
    });
  });
});

describe("cascadeClear", () => {
  it("leaves the first window exactly where its node puts it", () => {
    const base = placeNodeWindow(rect(900, 400), STAGE, SIZE);
    expect(cascadeClear(base, [], STAGE, SIZE)).toEqual(base);
  });

  it("moves a window off one it would otherwise hide", () => {
    const base = { x: 620, y: 200 };
    const spot = cascadeClear(base, [{ x: 620, y: 210 }], STAGE, SIZE);
    // Far enough apart that both title bars, and both close buttons, show.
    expect(Math.abs(spot.x - 620) >= 34 || Math.abs(spot.y - 210) >= 44).toBe(true);
  });

  it("leaves a window alone when it already clears the others", () => {
    const base = { x: 620, y: 200 };
    expect(cascadeClear(base, [{ x: 620, y: 700 }], STAGE, SIZE)).toEqual(base);
  });

  it("keeps a cascaded window on the stage however crowded it is", () => {
    const occupied = Array.from({ length: 8 }, (_, i) => ({ x: 620 + i, y: 200 + i }));
    const { x, y } = cascadeClear({ x: 620, y: 200 }, occupied, STAGE, SIZE);
    expect(x).toBeGreaterThanOrEqual(12);
    expect(y).toBeGreaterThanOrEqual(12);
    expect(x + SIZE.width).toBeLessThanOrEqual(STAGE.width - 12);
    expect(y + SIZE.height).toBeLessThanOrEqual(STAGE.height - 12);
  });

  it("stops cascading after the bounded number of visible title-bar offsets", () => {
    const base = { x: 620, y: 200 };
    const occupied = Array.from({ length: 7 }, (_, step) => ({
      x: base.x + 34 * step,
      y: base.y + 44 * step,
    }));

    expect(cascadeClear(base, occupied, { width: 2000, height: 1400 }, SIZE)).toEqual({
      x: base.x + 34 * 6,
      y: base.y + 44 * 6,
    });
  });
});
