import { PAGE } from "@core/app-shell/pages";
import type { PodGeom, Rect } from "@core/canvas/cableGeometry";
import { buildCables, type CableScene } from "@core/canvas/cableScene";
import { CANVAS_NODES } from "@core/canvas/canvasNodes";
import { describe, expect, it } from "vitest";

const mainPod: PodGeom = { center: { x: 500, y: 300 }, radius: 100 };

function rectAt(x: number, y: number, w = 80, h = 40): Rect {
  return { left: x - w / 2, right: x + w / 2, top: y - h / 2, bottom: y + h / 2 };
}

function allNodeRects(): Record<string, Rect> {
  return Object.fromEntries(
    CANVAS_NODES.map((node, index) => [node.key, rectAt(100 + index * 50, 100 + index * 30)]),
  );
}

function scene(overrides: Partial<CableScene> = {}): CableScene {
  return {
    stage: { width: 1600, height: 900 },
    mainPod,
    nodeRects: allNodeRects(),
    doneKeys: new Set<string>(),
    ...overrides,
  };
}

const ids = (geo: { cables: { id: string }[] }) => geo.cables.map((cable) => cable.id);

describe("buildCables", () => {
  it("carries the stage size through to the overlay", () => {
    const geo = buildCables(scene());
    expect({ w: geo.w, h: geo.h }).toEqual({ w: 1600, h: 900 });
  });

  it("draws exactly one cable per measured terminal", () => {
    expect(ids(buildCables(scene()))).toEqual(CANVAS_NODES.map((node) => node.key));
  });

  it("skips a terminal that has not been measured yet", () => {
    const nodeRects = allNodeRects();
    delete nodeRects[PAGE.SBOM];
    expect(ids(buildCables(scene({ nodeRects })))).not.toContain(PAGE.SBOM);
  });

  it("lands the pod end exactly on the pod surface", () => {
    const [cable] = buildCables(scene()).cables;
    const distance = Math.hypot(cable.x2 - mainPod.center.x, cable.y2 - mainPod.center.y);
    expect(distance).toBeCloseTo(mainPod.radius);
  });

  it("lands the terminal end on that terminal's border", () => {
    const [cable] = buildCables(scene({ nodeRects: { [PAGE.SOURCE]: rectAt(100, 300) } })).cables;
    expect(cable.x1).toBeCloseTo(140);
    expect(cable.y1).toBeCloseTo(300);
  });

  it("names each cable's stage", () => {
    const geo = buildCables(scene());
    for (const node of CANVAS_NODES) {
      expect(geo.cables.find((cable) => cable.id === node.key)?.stageKey).toBe(node.key);
    }
  });

  it("lights only cables whose step is done", () => {
    const geo = buildCables(scene({ doneKeys: new Set([PAGE.SOURCE, PAGE.BUILD]) }));
    const connected = geo.cables.filter((cable) => cable.connected).map((cable) => cable.id);
    expect(connected).toEqual([PAGE.SOURCE, PAGE.BUILD]);
  });
});
