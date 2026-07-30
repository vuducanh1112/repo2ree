import { PAGE } from "@core/app-shell/pages";
import type { PodGeom, Rect } from "@core/canvas/cableGeometry";
import {
  buildCables,
  buildExperimentCables,
  type CableScene,
  type CoreCableTarget,
  type ExperimentCableScene,
} from "@core/canvas/cableScene";
import { CANVAS_NODES } from "@core/canvas/canvasNodes";
import { describe, expect, it } from "vitest";

const mainPod: PodGeom = { center: { x: 500, y: 300 }, radius: 100 };
const innerPod: PodGeom = { center: { x: 1200, y: 300 }, radius: 60 };
const corePod: PodGeom = { center: { x: 1900, y: 300 }, radius: 40 };

function rectAt(x: number, y: number, w = 80, h = 40): Rect {
  return { left: x - w / 2, right: x + w / 2, top: y - h / 2, bottom: y + h / 2 };
}

/** A panel box for every canvas node, so nothing is skipped for being unmeasured. */
function allNodeRects(): Record<string, Rect> {
  return Object.fromEntries(
    CANVAS_NODES.map((node, index) => [node.key, rectAt(100 + index * 50, 100 + index * 30)]),
  );
}

function scene(overrides: Partial<CableScene> = {}): CableScene {
  return {
    stage: { width: 1600, height: 900 },
    mainPod,
    projectionPods: {},
    nodeRects: allNodeRects(),
    doneKeys: new Set<string>(),
    exploded: false,
    ...overrides,
  };
}

const ids = (geo: { cables: { id: string }[] }) => geo.cables.map((cable) => cable.id);

describe("buildCables, assembled", () => {
  it("carries the stage size through to the overlay", () => {
    const geo = buildCables(scene());
    expect({ w: geo.w, h: geo.h }).toEqual({ w: 1600, h: 900 });
  });

  it("draws exactly one membership cable per node, and no chain", () => {
    expect(ids(buildCables(scene()))).toEqual(CANVAS_NODES.map((node) => node.key));
  });

  it("skips a node that has not been measured yet", () => {
    const nodeRects = allNodeRects();
    delete nodeRects[PAGE.SBOM];
    expect(ids(buildCables(scene({ nodeRects })))).not.toContain(PAGE.SBOM);
  });

  it("lands the pod end exactly on the pod surface", () => {
    const [cable] = buildCables(scene()).cables;
    const dist = Math.hypot(cable.x2 - mainPod.center.x, cable.y2 - mainPod.center.y);
    expect(dist).toBeCloseTo(mainPod.radius);
  });

  it("lands the panel end on that panel's border", () => {
    const geo = buildCables(scene({ nodeRects: { [PAGE.SOURCE]: rectAt(100, 300) } }));
    const [cable] = geo.cables;
    // The pod is due right of this panel, so the knob rides the right edge.
    expect(cable.x1).toBeCloseTo(140);
    expect(cable.y1).toBeCloseTo(300);
  });

  it("takes each cable's colour from its node, not from its state", () => {
    const geo = buildCables(scene());
    for (const node of CANVAS_NODES) {
      expect(geo.cables.find((cable) => cable.id === node.key)?.color).toBe(node.color);
    }
  });

  it("lights only the cables whose step is done", () => {
    const geo = buildCables(scene({ doneKeys: new Set([PAGE.SOURCE, PAGE.BUILD]) }));
    const connected = geo.cables.filter((cable) => cable.connected).map((cable) => cable.id);
    expect(connected).toEqual([PAGE.SOURCE, PAGE.BUILD]);
  });

  it("ignores the projection pods entirely — they are the decomposed view's", () => {
    const withColumns = buildCables(scene({ projectionPods: { inner: innerPod, core: corePod } }));
    expect(withColumns).toEqual(buildCables(scene()));
  });
});

describe("buildCables, decomposed", () => {
  const exploded = (overrides: Partial<CableScene> = {}) =>
    buildCables(
      scene({ exploded: true, projectionPods: { inner: innerPod, core: corePod }, ...overrides }),
    );

  it("draws the spine before the membership cables, so it renders underneath", () => {
    expect(ids(exploded()).slice(0, 4)).toEqual([
      "chain-outer-source",
      "chain-source-inner",
      "chain-inner-activation",
      "chain-activation-core",
    ]);
  });

  it("withdraws the membership cable of every panel the chain already wires", () => {
    const drawn = ids(exploded());
    for (const key of [PAGE.SOURCE, PAGE.BUILD, PAGE.ACTIVATION]) {
      expect(drawn).not.toContain(key);
    }
  });

  it("withdraws the Experiments cable, which the core satellites take over", () => {
    expect(ids(exploded())).not.toContain(PAGE.EXPERIMENTS);
  });

  it("keeps every other node's membership cable", () => {
    const withdrawn = new Set<string>([PAGE.SOURCE, PAGE.BUILD, PAGE.ACTIVATION, PAGE.EXPERIMENTS]);
    const expected = CANVAS_NODES.map((node) => node.key).filter((key) => !withdrawn.has(key));
    expect(ids(exploded()).slice(4)).toEqual(expected);
  });

  it("anchors an inner-shell node to the inner column, not the main pod", () => {
    const cable = exploded().cables.find((entry) => entry.id === PAGE.SBOM);
    if (!cable) throw new Error("no SBOM cable");
    const dist = Math.hypot(cable.x2 - innerPod.center.x, cable.y2 - innerPod.center.y);
    expect(dist).toBeCloseTo(innerPod.radius);
  });

  it("keeps outer-shell nodes on the main pod — the outer shell is the artifact", () => {
    const cable = exploded().cables.find((entry) => entry.id === PAGE.SEAL);
    if (!cable) throw new Error("no Seal cable");
    const dist = Math.hypot(cable.x2 - mainPod.center.x, cable.y2 - mainPod.center.y);
    expect(dist).toBeCloseTo(mainPod.radius);
  });

  it("falls back to the main pod when a column has not been measured", () => {
    const cable = exploded({ projectionPods: { core: corePod } }).cables.find(
      (entry) => entry.id === PAGE.SBOM,
    );
    if (!cable) throw new Error("no SBOM cable");
    const dist = Math.hypot(cable.x2 - mainPod.center.x, cable.y2 - mainPod.center.y);
    expect(dist).toBeCloseTo(mainPod.radius);
  });

  it("drops a chain link whose end is missing, keeping the rest of the spine", () => {
    // No core column measured yet: the activation->core link cannot be drawn.
    const drawn = ids(exploded({ projectionPods: { inner: innerPod } }));
    expect(drawn).toContain("chain-inner-activation");
    expect(drawn).not.toContain("chain-activation-core");
  });

  it("drops the whole spine when no column has been measured", () => {
    const drawn = ids(exploded({ projectionPods: {} }));
    expect(drawn.filter((id) => id.startsWith("chain-"))).toEqual(["chain-outer-source"]);
  });

  it("lights each chain link from the step it represents", () => {
    const geo = exploded({ doneKeys: new Set([PAGE.SOURCE]) });
    const byId = new Map(geo.cables.map((cable) => [cable.id, cable]));
    expect(byId.get("chain-outer-source")?.connected).toBe(true);
    expect(byId.get("chain-source-inner")?.connected).toBe(false);
  });
});

describe("buildExperimentCables", () => {
  const corePodAtOrigin: PodGeom = { center: { x: 300, y: 300 }, radius: 50 };
  const target = (key: string, connected = false): CoreCableTarget => ({
    key,
    connected,
    color: "#4f46e5",
    shadow: "#3730a3",
  });

  function experimentScene(overrides: Partial<ExperimentCableScene> = {}): ExperimentCableScene {
    return {
      stage: { width: 800, height: 600 },
      corePod: corePodAtOrigin,
      targets: [target("exp-1"), target("exp-2", true)],
      satelliteRects: { "exp-1": rectAt(100, 300), "exp-2": rectAt(500, 300) },
      ...overrides,
    };
  }

  it("draws one cable per satellite, in target order", () => {
    expect(ids(buildExperimentCables(experimentScene()))).toEqual(["exp-1", "exp-2"]);
  });

  it("skips a satellite that has not been measured", () => {
    const geo = buildExperimentCables(
      experimentScene({ satelliteRects: { "exp-2": rectAt(500, 300) } }),
    );
    expect(ids(geo)).toEqual(["exp-2"]);
  });

  it("lands every cable on the core surface", () => {
    for (const cable of buildExperimentCables(experimentScene()).cables) {
      const dist = Math.hypot(
        cable.x2 - corePodAtOrigin.center.x,
        cable.y2 - corePodAtOrigin.center.y,
      );
      expect(dist).toBeCloseTo(corePodAtOrigin.radius);
    }
  });

  it("takes the lit/dim state from the target", () => {
    const geo = buildExperimentCables(experimentScene());
    expect(geo.cables.map((cable) => cable.connected)).toEqual([false, true]);
  });

  it("approaches the core from whichever side the satellite sits on", () => {
    const [left, right] = buildExperimentCables(experimentScene()).cables;
    expect(left.x2).toBeLessThan(corePodAtOrigin.center.x);
    expect(right.x2).toBeGreaterThan(corePodAtOrigin.center.x);
  });

  it("draws nothing when there are no experiments, but keeps the stage size", () => {
    const geo = buildExperimentCables(experimentScene({ targets: [] }));
    expect(geo).toEqual({ cables: [], w: 800, h: 600 });
  });
});
