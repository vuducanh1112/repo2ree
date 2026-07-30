import { describe, expect, it } from "vitest";
import { cableHl, cablePath } from "./cableGeometry";

// Both helpers emit an SVG cubic path. The tests assert the properties the look
// depends on — endpoints, droop direction, the highlight's offset — rather than
// the exact `d` string, which is a rendering detail free to change.
function numbers(path: string): number[] {
  return (path.match(/-?\d+(\.\d+)?/g) ?? []).map(Number);
}

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
