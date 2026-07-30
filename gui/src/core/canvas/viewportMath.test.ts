import { describe, expect, it } from "vitest";
import {
  clampZoom,
  dragOffset,
  exceedsDragThreshold,
  type StageBox,
  type Transform,
  ZOOM_MAX,
  ZOOM_MIN,
  zoomToward,
} from "./viewportMath";

const stage: StageBox = { left: 0, top: 0, width: 1000, height: 600 };
const centre = { x: 500, y: 300 };
const identity: Transform = { x: 0, y: 0, z: 1 };

const IN = -1;
const OUT = 1;

describe("clampZoom", () => {
  it("passes anything already in range", () => {
    expect(clampZoom(1)).toBe(1);
    expect(clampZoom(ZOOM_MIN)).toBe(ZOOM_MIN);
    expect(clampZoom(ZOOM_MAX)).toBe(ZOOM_MAX);
  });

  it("clamps either end", () => {
    expect(clampZoom(0.01)).toBe(ZOOM_MIN);
    expect(clampZoom(99)).toBe(ZOOM_MAX);
  });
});

describe("zoomToward", () => {
  it("scales in on a notch up and out on a notch down", () => {
    expect(zoomToward(identity, centre, stage, IN).z).toBeGreaterThan(1);
    expect(zoomToward(identity, centre, stage, OUT).z).toBeLessThan(1);
  });

  it("does not pan when the pointer is already at the world centre", () => {
    const next = zoomToward(identity, centre, stage, IN);
    expect(next.x).toBe(0);
    expect(next.y).toBe(0);
  });

  it("keeps the point under the cursor under the cursor", () => {
    // The world point at the pointer is (pointer - centre - pan) / z. Zooming
    // about that pointer must leave it unchanged.
    const pointer = { x: 800, y: 150 };
    const worldAt = (tf: Transform) => ({
      x: (pointer.x - stage.left - stage.width / 2 - tf.x) / tf.z,
      y: (pointer.y - stage.top - stage.height / 2 - tf.y) / tf.z,
    });
    const before = worldAt(identity);
    const after = worldAt(zoomToward(identity, pointer, stage, IN));

    expect(after.x).toBeCloseTo(before.x);
    expect(after.y).toBeCloseTo(before.y);
  });

  it("returns to where it started after a notch each way", () => {
    const pointer = { x: 800, y: 150 };
    const roundTrip = zoomToward(zoomToward(identity, pointer, stage, IN), pointer, stage, OUT);

    expect(roundTrip.z).toBeCloseTo(1);
    expect(roundTrip.x).toBeCloseTo(0);
    expect(roundTrip.y).toBeCloseTo(0);
  });

  it("respects the zoom limits", () => {
    let tf: Transform = identity;
    for (let i = 0; i < 40; i++) tf = zoomToward(tf, centre, stage, IN);
    expect(tf.z).toBe(ZOOM_MAX);

    tf = identity;
    for (let i = 0; i < 40; i++) tf = zoomToward(tf, centre, stage, OUT);
    expect(tf.z).toBe(ZOOM_MIN);
  });

  it("is a no-op at a limit, rather than panning", () => {
    // The clamp makes the ratio 0, so nothing moves. This is exactly the case
    // that fires no `transitionend` and needs the measure loop's own timeout.
    const atMax: Transform = { x: 40, y: -20, z: ZOOM_MAX };
    expect(zoomToward(atMax, { x: 800, y: 150 }, stage, IN)).toEqual(atMax);
  });

  it("measures the pointer against the stage's own origin, not the page's", () => {
    const offsetStage: StageBox = { left: 100, top: 50, width: 1000, height: 600 };
    const offsetCentre = { x: 100 + 500, y: 50 + 300 };
    expect(zoomToward(identity, offsetCentre, offsetStage, IN)).toEqual(
      zoomToward(identity, centre, stage, IN),
    );
  });
});

describe("exceedsDragThreshold", () => {
  it("ignores the jitter of a click", () => {
    expect(exceedsDragThreshold(0, 0)).toBe(false);
    expect(exceedsDragThreshold(3, 0)).toBe(false);
  });

  it("measures distance, not either axis alone", () => {
    // 4 across and 4 down is ~5.7px of travel, past the threshold, even though
    // neither axis is.
    expect(exceedsDragThreshold(4, 4)).toBe(true);
    expect(exceedsDragThreshold(-5, 0)).toBe(true);
  });
});

describe("dragOffset", () => {
  it("adds the travel to where the node started", () => {
    expect(dragOffset({ x: 10, y: 20 }, 5, -5, 1)).toEqual({ x: 15, y: 15 });
  });

  it("divides by the zoom so a card tracks the cursor 1:1 at any scale", () => {
    // Zoomed to 2x, 100 screen px is 50 world px.
    expect(dragOffset({ x: 0, y: 0 }, 100, 40, 2)).toEqual({ x: 50, y: 20 });
    expect(dragOffset({ x: 0, y: 0 }, 100, 40, 0.5)).toEqual({ x: 200, y: 80 });
  });
});
