import { PAGE } from "@core/app-shell/pages";
import {
  DEFAULT_LAYOUT,
  isDefaultLayout,
  LAYOUT_VERSION,
  nodeOffsetAfterDrag,
  offsetOf,
  parseStoredLayout,
  placedNode,
  placedNodes,
  serializeLayout,
  withNodeMoved,
  withNodeReset,
} from "@core/canvas/canvasLayout";
import {
  CANVAS_NODES,
  canvasWorldBounds,
  floorPointFromScreen,
  screenPointFromFloor,
} from "@core/canvas/canvasNodes";
import { describe, expect, it } from "vitest";

function nodeFor(page: (typeof CANVAS_NODES)[number]["key"]) {
  const node = CANVAS_NODES.find((entry) => entry.key === page);
  if (!node) throw new Error(`no canvas node for ${page}`);
  return node;
}

describe("floor projection", () => {
  it("round-trips every node's own position", () => {
    for (const node of CANVAS_NODES) {
      const back = floorPointFromScreen(screenPointFromFloor(node));
      expect(back.x).toBeCloseTo(node.x, 6);
      expect(back.y).toBeCloseTo(node.y, 6);
    }
  });

  it("round-trips points well off the ring, where a drag can put them", () => {
    for (const point of [
      { x: 0, y: 0 },
      { x: -1400, y: -900 },
      { x: 1400, y: 900 },
      { x: 320, y: -1200 },
    ]) {
      const back = floorPointFromScreen(screenPointFromFloor(point));
      expect(back.x).toBeCloseTo(point.x, 6);
      expect(back.y).toBeCloseTo(point.y, 6);
    }
  });

  it("foreshortens depth and leaves width alone at the floor origin", () => {
    expect(screenPointFromFloor({ x: 100, y: 0 })).toEqual({ x: 100, y: 0 });
    expect(screenPointFromFloor({ x: 0, y: 100 }).y).toBeLessThan(100);
  });
});

describe("layout offsets", () => {
  it("starts at the default, which is no offsets at all", () => {
    expect(isDefaultLayout(DEFAULT_LAYOUT)).toBe(true);
    expect(offsetOf(DEFAULT_LAYOUT, PAGE.SEAL)).toEqual({ dx: 0, dy: 0 });
  });

  it("places a moved node away from where the ring put it", () => {
    const seal = nodeFor(PAGE.SEAL);
    const layout = withNodeMoved(DEFAULT_LAYOUT, PAGE.SEAL, { dx: 120, dy: -40 });
    expect(placedNode(seal, layout)).toMatchObject({ x: seal.x + 120, y: seal.y - 40 });
  });

  it("leaves untouched nodes identical, not merely equal", () => {
    // Placement runs on every render; an untouched node must not churn its
    // identity and invalidate everything memoised downstream of it.
    const layout = withNodeMoved(DEFAULT_LAYOUT, PAGE.SEAL, { dx: 10, dy: 10 });
    const build = nodeFor(PAGE.BUILD);
    expect(placedNode(build, layout)).toBe(build);
  });

  it("treats moving a node back to zero as no longer being moved", () => {
    const moved = withNodeMoved(DEFAULT_LAYOUT, PAGE.BUILD, { dx: 40, dy: 0 });
    expect(isDefaultLayout(moved)).toBe(false);
    expect(isDefaultLayout(withNodeMoved(moved, PAGE.BUILD, { dx: 0, dy: 0 }))).toBe(true);
    expect(isDefaultLayout(withNodeReset(moved, PAGE.BUILD))).toBe(true);
  });

  it("places the whole bench in one pass", () => {
    const layout = withNodeMoved(DEFAULT_LAYOUT, PAGE.SOURCE, { dx: 5, dy: 5 });
    expect(placedNodes(layout)).toHaveLength(CANVAS_NODES.length);
    expect(placedNodes(layout)[0].x).toBe(nodeFor(PAGE.SOURCE).x + 5);
  });
});

describe("dragging", () => {
  it("moves a panel by what the pointer moved on screen, wherever it stands", () => {
    // The floor is tilted and in perspective, so equal screen deltas are
    // unequal bench distances. What has to hold is that the panel ends up under
    // the pointer — which is a statement about the projection, not the floor.
    for (const node of [nodeFor(PAGE.SEAL), nodeFor(PAGE.EVALUATE), nodeFor(PAGE.SOURCE)]) {
      const delta = { dx: 90, dy: -60 };
      const offset = nodeOffsetAfterDrag(node, { dx: 0, dy: 0 }, delta);
      const before = screenPointFromFloor(node);
      const after = screenPointFromFloor(placedNode(node, { [node.key]: offset }));
      expect(after.x - before.x).toBeCloseTo(delta.dx, 6);
      expect(after.y - before.y).toBeCloseTo(delta.dy, 6);
    }
  });

  it("accumulates from the offset the panel already carries", () => {
    const node = nodeFor(PAGE.BUILD);
    const first = nodeOffsetAfterDrag(node, { dx: 0, dy: 0 }, { dx: 40, dy: 0 });
    const second = nodeOffsetAfterDrag(node, first, { dx: 40, dy: 0 });
    const inOneGo = nodeOffsetAfterDrag(node, { dx: 0, dy: 0 }, { dx: 80, dy: 0 });
    expect(second.dx).toBeCloseTo(inOneGo.dx, 6);
    expect(second.dy).toBeCloseTo(inOneGo.dy, 6);
  });

  it("is a no-op for a pointer that has not moved", () => {
    const offset = nodeOffsetAfterDrag(nodeFor(PAGE.SBOM), { dx: 0, dy: 0 }, { dx: 0, dy: 0 });
    expect(offset.dx).toBeCloseTo(0, 6);
    expect(offset.dy).toBeCloseTo(0, 6);
  });
});

describe("stored layouts", () => {
  it("round-trips an arrangement", () => {
    const layout = withNodeMoved(DEFAULT_LAYOUT, PAGE.SEAL, { dx: 12, dy: -8 });
    expect(parseStoredLayout(serializeLayout(layout))).toEqual(layout);
  });

  it("falls back to the default when there is nothing stored", () => {
    expect(parseStoredLayout(null)).toEqual(DEFAULT_LAYOUT);
    expect(parseStoredLayout("")).toEqual(DEFAULT_LAYOUT);
  });

  it("discards an arrangement written against a different default ring", () => {
    const stale = JSON.stringify({
      version: LAYOUT_VERSION + 1,
      offsets: { [PAGE.SEAL]: { dx: 30, dy: 30 } },
    });
    expect(parseStoredLayout(stale)).toEqual(DEFAULT_LAYOUT);
  });

  it("survives anything that is not a layout at all", () => {
    for (const raw of ["{", "null", "[]", '"nope"', '{"version":1}', '{"version":1,"offsets":3}']) {
      expect(parseStoredLayout(raw)).toEqual(DEFAULT_LAYOUT);
    }
  });

  it("drops entries for nodes that no longer exist and offsets that are not numbers", () => {
    const raw = JSON.stringify({
      version: LAYOUT_VERSION,
      offsets: {
        [PAGE.BUILD]: { dx: 20, dy: 5 },
        gone: { dx: 10, dy: 10 },
        [PAGE.SBOM]: { dx: "12", dy: 4 },
        [PAGE.SEAL]: { dx: Number.NaN, dy: 0 },
      },
    });
    expect(parseStoredLayout(raw)).toEqual({ [PAGE.BUILD]: { dx: 20, dy: 5 } });
  });
});

describe("bounds under an arrangement", () => {
  it("follows a panel the user has dragged away from the ring", () => {
    // `fitView` has to frame what is actually on the bench, not where the ring
    // would have put it — otherwise moving a panel outward hides it.
    const layout = withNodeMoved(DEFAULT_LAYOUT, PAGE.SOURCE, { dx: -600, dy: 0 });
    const moved = canvasWorldBounds(placedNodes(layout));
    expect(moved.left).toBeLessThan(canvasWorldBounds().left);
  });
});
