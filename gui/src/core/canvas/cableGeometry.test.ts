import { describe, expect, it } from "vitest";
import {
  cableHl,
  cablePath,
  edgeToward,
  intercept,
  type Matrix2D,
  POD_CX,
  POD_CY,
  POD_SR,
  type PodGeom,
  podGeomFromMatrix,
  type Rect,
  rectCenter,
} from "./cableGeometry";

// Both helpers emit an SVG cubic path. The tests assert the properties the look
// depends on — endpoints, droop direction, the highlight's offset — rather than
// the exact `d` string, which is a rendering detail free to change.
function numbers(path: string): number[] {
  return (path.match(/-?\d+(\.\d+)?/g) ?? []).map(Number);
}

const identity: Matrix2D = { a: 1, b: 0, c: 0, d: 1, e: 0, f: 0 };
const noOrigin = { x: 0, y: 0 };

describe("podGeomFromMatrix", () => {
  it("puts an untransformed pod at its viewBox centre, at its viewBox radius", () => {
    expect(podGeomFromMatrix(identity, noOrigin)).toEqual({
      center: { x: POD_CX, y: POD_CY },
      radius: POD_SR,
    });
  });

  it("measures relative to the stage, not the page", () => {
    const pod = podGeomFromMatrix(identity, { x: 40, y: 25 });
    expect(pod.center).toEqual({ x: POD_CX - 40, y: POD_CY - 25 });
    // Subtracting an origin shifts the sphere; it does not resize it.
    expect(pod.radius).toBe(POD_SR);
  });

  it("picks up the scale the matrix carries", () => {
    const halved: Matrix2D = { ...identity, a: 0.5, d: 0.5 };
    const pod = podGeomFromMatrix(halved, noOrigin);
    expect(pod.radius).toBeCloseTo(POD_SR / 2);
    expect(pod.center).toEqual({ x: POD_CX / 2, y: POD_CY / 2 });
  });

  it("adds the matrix's own translation", () => {
    const moved: Matrix2D = { ...identity, e: 100, f: -50 };
    expect(podGeomFromMatrix(moved, noOrigin).center).toEqual({
      x: POD_CX + 100,
      y: POD_CY - 50,
    });
  });

  it("takes the radius from the transformed distance, so rotation cannot shrink it", () => {
    // A quarter turn: the edge point swings around but stays POD_SR away.
    const rotated: Matrix2D = { a: 0, b: 1, c: -1, d: 0, e: 0, f: 0 };
    expect(podGeomFromMatrix(rotated, noOrigin).radius).toBeCloseTo(POD_SR);
  });
});

describe("intercept", () => {
  const pod: PodGeom = { center: { x: 100, y: 100 }, radius: 20 };

  it("returns a point exactly one radius from the centre", () => {
    const point = intercept(pod, 400, 250);
    expect(Math.hypot(point.x - 100, point.y - 100)).toBeCloseTo(20);
  });

  it("points at the target", () => {
    expect(intercept(pod, 400, 100)).toEqual({ x: 120, y: 100 });
    expect(intercept(pod, 100, -50)).toEqual({ x: 100, y: 80 });
  });

  it("degenerates to the centre for a target on the centre, rather than to NaN", () => {
    // There is no ray to follow, so the `|| 1` guard yields the centre itself.
    // Off the surface, but finite — a zero-length cable beats an unrenderable one.
    expect(intercept(pod, 100, 100)).toEqual({ x: 100, y: 100 });
  });

  it("ignores how far away the target is", () => {
    expect(intercept(pod, 1000, 1000)).toEqual(intercept(pod, 101, 101));
  });
});

describe("edgeToward", () => {
  // 80 wide, 40 tall, centred on (100, 100).
  const rect: Rect = { left: 60, right: 140, top: 80, bottom: 120 };

  it("rides the edge facing the target", () => {
    expect(edgeToward(rect, 500, 100)).toEqual({ x: 140, y: 100 });
    expect(edgeToward(rect, -500, 100)).toEqual({ x: 60, y: 100 });
    expect(edgeToward(rect, 100, -500)).toEqual({ x: 100, y: 80 });
    expect(edgeToward(rect, 100, 500)).toEqual({ x: 100, y: 120 });
  });

  it("lands on the border, whatever the angle", () => {
    for (const target of [
      { x: 900, y: 700 },
      { x: -300, y: 400 },
      { x: 250, y: -80 },
    ]) {
      const point = edgeToward(rect, target.x, target.y);
      const onVertical =
        Math.abs(point.x - rect.left) < 1e-9 || Math.abs(point.x - rect.right) < 1e-9;
      const onHorizontal =
        Math.abs(point.y - rect.top) < 1e-9 || Math.abs(point.y - rect.bottom) < 1e-9;
      expect(onVertical || onHorizontal).toBe(true);
    }
  });

  it("leaves the corner exactly at the corner", () => {
    // The rect is twice as wide as it is tall, so a 2:1 target hits the corner.
    expect(edgeToward(rect, 100 + 400, 100 + 200)).toEqual({ x: 140, y: 120 });
  });

  it("collapses to the centre for a degenerate box", () => {
    const flat: Rect = { left: 100, right: 100, top: 80, bottom: 120 };
    expect(edgeToward(flat, 500, 500)).toEqual({ x: 100, y: 100 });
  });

  it("collapses to the centre for a target on the centre", () => {
    expect(edgeToward(rect, 100, 100)).toEqual({ x: 100, y: 100 });
  });
});

describe("rectCenter", () => {
  it("averages the edges", () => {
    expect(rectCenter({ left: 60, right: 140, top: 80, bottom: 120 })).toEqual({ x: 100, y: 100 });
  });

  it("handles negative coordinates, which panning produces", () => {
    expect(rectCenter({ left: -40, right: 40, top: -100, bottom: -20 })).toEqual({ x: 0, y: -60 });
  });
});

describe("cablePath", () => {
  it("starts and ends exactly on the points it is given", () => {
    const d = cablePath(10, 20, 110, 80);
    expect(d.startsWith("M 10 20 C")).toBe(true);
    expect(d.endsWith("110 80")).toBe(true);
  });

  it("droops: both control points sit below the line, as gravity would", () => {
    const [, , cy1, , cy2] = numbers(cablePath(0, 0, 100, 0)).slice(2);
    expect(cy1).toBeGreaterThan(0);
    expect(cy2).toBeGreaterThan(0);
  });

  it("droops further the longer the cable", () => {
    const shortDroop = numbers(cablePath(0, 0, 50, 0))[3];
    const longDroop = numbers(cablePath(0, 0, 500, 0))[3];
    expect(longDroop).toBeGreaterThan(shortDroop);
  });

  it("has no droop at zero length", () => {
    expect(cablePath(40, 40, 40, 40)).toBe("M 40 40 C 40 40, 40 40, 40 40");
  });

  it("droops downward regardless of which end is left", () => {
    // Nodes sit on both sides of the pod, so cables run right-to-left too.
    const [, , cy1] = numbers(cablePath(100, 0, 0, 0)).slice(2);
    expect(cy1).toBeGreaterThan(0);
  });
});

describe("cableHl", () => {
  it("rides above the cable it highlights, at both ends", () => {
    const d = cableHl(10, 20, 110, 80);
    expect(d.startsWith("M 10 18.6 C")).toBe(true);
    expect(d.endsWith("110 78.6")).toBe(true);
  });

  it("keeps the same droop shape, so the highlight tracks the cable", () => {
    const cable = numbers(cablePath(0, 0, 300, 0));
    const highlight = numbers(cableHl(0, 0, 300, 0));
    // Control-point x values are identical; only y is lifted.
    expect(highlight[2]).toBeCloseTo(cable[2]);
    expect(highlight[4]).toBeCloseTo(cable[4]);
    expect(highlight[3]).toBeLessThan(cable[3]);
  });
});
