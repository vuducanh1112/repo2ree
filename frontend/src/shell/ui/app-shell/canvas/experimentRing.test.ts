import { describe, expect, it } from "vitest";
import { satellitePositions } from "./experimentRing";

describe("satellitePositions", () => {
  it("returns nothing when there are no experiments and no add-slot", () => {
    expect(satellitePositions(0, false)).toEqual([]);
  });

  it("reserves a trailing slot for the add-ghost", () => {
    // 2 experiments + the add-ghost = 3 ring slots; the add-ghost is last.
    expect(satellitePositions(2, true)).toHaveLength(3);
    expect(satellitePositions(2, false)).toHaveLength(2);
  });

  it("places the first slot due north of the core", () => {
    const [first] = satellitePositions(4, false);
    expect(first.x).toBeCloseTo(0);
    expect(first.y).toBeLessThan(0);
  });

  it("spreads slots evenly on a ring centred on the origin", () => {
    const positions = satellitePositions(4, false);
    const radii = positions.map((p) => Math.hypot(p.x, p.y));
    // All on one ring (same radius)...
    for (const r of radii) expect(r).toBeCloseTo(radii[0]);
    // ...and 4 evenly-spaced slots land at the cardinal points.
    const [north, east, south, west] = positions;
    expect(north.y).toBeLessThan(0);
    expect(east.x).toBeGreaterThan(0);
    expect(south.y).toBeGreaterThan(0);
    expect(west.x).toBeLessThan(0);
  });

  it("pushes the ring out as the population grows so cards keep their gap", () => {
    const small = Math.hypot(...tupleFirst(satellitePositions(3, false)));
    const large = Math.hypot(...tupleFirst(satellitePositions(10, false)));
    expect(large).toBeGreaterThan(small);
  });
});

function tupleFirst(positions: { x: number; y: number }[]): [number, number] {
  return [positions[0].x, positions[0].y];
}
