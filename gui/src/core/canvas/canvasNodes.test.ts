/* biome-ignore-all lint/style/useNamingConvention: receipt fixtures intentionally use wire field names */
import { PAGE } from "@core/app-shell/pages";
import {
  activeNode,
  CANVAS_NODES,
  canvasWorldBounds,
  isNodeActive,
  isNodeDone,
  isNodeStale,
  nodeCardBox,
  nodeOverview,
  nodeScale,
  nodeScreenBox,
  nodeSummary,
  RING,
  SCENE_DEPTH,
} from "@core/canvas/canvasNodes";
import { fitBounds } from "@core/canvas/viewportMath";
import { parseAuthorReceipts } from "@core/receipts/authorReceipts";
import { createEmptyReeExperiment } from "@core/ree/ReeSpec";
import {
  createEmptyReeEditorViewModel,
  patchReeEditorViewModel,
  type ReeEditorViewModelPatch,
} from "@core/ree-editor/reeEditorViewModel";
import type { SourceRepoMetadata } from "@core/workspace/WorkspaceTypes";
import { describe, expect, it } from "vitest";

function nodeFor(page: (typeof CANVAS_NODES)[number]["key"]) {
  const node = CANVAS_NODES.find((entry) => entry.key === page);
  if (!node) throw new Error(`no canvas node for ${page}`);
  return node;
}

/** The summary rows a node shows, as a label -> value map. */
function summaryOf(
  page: (typeof CANVAS_NODES)[number]["key"],
  ree: ReeEditorViewModelPatch = {},
  sourceRepo?: SourceRepoMetadata,
): Record<string, string | null> {
  const rows = nodeSummary(
    nodeFor(page),
    patchReeEditorViewModel(createEmptyReeEditorViewModel(), ree),
    sourceRepo,
  );
  return Object.fromEntries(rows.map((row) => [row.label, row.value]));
}

describe("CANVAS_NODES", () => {
  it("carries one node per pipeline page, and no workbench node", () => {
    // The workbench is the lab the pod sits in, not a node orbiting it.
    expect(CANVAS_NODES.map((node) => node.key)).toEqual([
      PAGE.SOURCE,
      PAGE.METADATA,
      PAGE.HBOM,
      PAGE.EVALUATE,
      PAGE.BUILD,
      PAGE.SBOM,
      PAGE.ACTIVATION,
      PAGE.EXPERIMENTS,
      PAGE.SEAL,
      PAGE.ARCHIVE,
    ]);
  });

  it("lifts every assembled panel above its floor anchor", () => {
    for (const node of CANVAS_NODES) expect(node.standHeight).toBeGreaterThan(0);
  });
});

describe("ring placement", () => {
  it("walks the authoring pipeline clockwise around the bench", () => {
    // The ring reads as the sequence: every step stands further round than the
    // one before it, so the canvas and the status bar cannot disagree about
    // what follows what.
    const authoring = CANVAS_NODES.filter((node) => node.key !== PAGE.ARCHIVE);
    const angles = authoring.map((node) => node.angle);
    const unwrapped = angles.map((angle) => (angle < angles[0] ? angle + 360 : angle));
    expect(unwrapped).toEqual([...unwrapped].sort((a, b) => a - b));
  });

  it("finishes authoring at the seal, dead centre in front of the pod", () => {
    const seal = nodeFor(PAGE.SEAL);
    expect(seal.angle).toBe(180);
    expect(seal.x).toBe(0);
    // Positive y is the near side of the bench: closest to the viewer, and the
    // largest a panel renders before the billboard correction evens it out.
    expect(seal.y).toBe(RING.ry);
  });

  it("puts archive past the seal, off the authoring arc", () => {
    expect(nodeFor(PAGE.ARCHIVE).angle).toBeGreaterThan(nodeFor(PAGE.SEAL).angle);
  });

  it("leaves a sector of the ring open", () => {
    // The gap between the last node and the first is the canvas's breathing
    // room — a horseshoe, not a closed ring.
    const last = nodeFor(PAGE.ARCHIVE).angle;
    const first = nodeFor(PAGE.SOURCE).angle;
    expect(first - last).toBeGreaterThan(40);
  });

  it("places every node on the declared ellipse", () => {
    for (const node of CANVAS_NODES) {
      const onRing = (node.x / RING.rx) ** 2 + (node.y / RING.ry) ** 2;
      expect(onRing).toBeCloseTo(1, 2);
    }
  });

  it("stands no two panels on top of each other", () => {
    // Card faces only: a strut crossing a neighbour's deck plate is fine, two
    // readable faces overlapping is not. The conservative card box makes this a
    // real guarantee rather than a near-miss.
    for (const a of CANVAS_NODES) {
      for (const b of CANVAS_NODES) {
        if (a.key === b.key) continue;
        const boxA = nodeCardBox(a);
        const boxB = nodeCardBox(b);
        const overlaps =
          boxA.left < boxB.right &&
          boxB.left < boxA.right &&
          boxA.top < boxB.bottom &&
          boxB.top < boxA.bottom;
        expect(`${a.key}/${b.key}: ${overlaps}`).toBe(`${a.key}/${b.key}: false`);
      }
    }
  });
});

describe("billboard correction", () => {
  it("cancels perspective so every panel renders the same size", () => {
    // Each node's own perspective factor times its correction must come to 1,
    // whichever side of the bench it stands on.
    for (const node of CANVAS_NODES) {
      const perspective = SCENE_DEPTH / (SCENE_DEPTH - node.y * Math.sin((54 * Math.PI) / 180));
      expect(perspective * nodeScale(node)).toBeCloseTo(1, 6);
    }
  });

  it("shrinks near panels and enlarges far ones", () => {
    expect(nodeScale(nodeFor(PAGE.SEAL))).toBeLessThan(1);
    expect(nodeScale(nodeFor(PAGE.EVALUATE))).toBeGreaterThan(1);
  });
});

describe("canvasWorldBounds", () => {
  it("frames the scene the nodes actually occupy", () => {
    const bounds = canvasWorldBounds();
    // `left + width` reconstructs the right edge through one more float op than
    // the box came from, so compare with a sub-pixel tolerance rather than
    // asserting on the last bit.
    const within = (value: number, limit: number) =>
      expect(value).toBeLessThanOrEqual(limit + 1e-6);
    for (const node of CANVAS_NODES) {
      const box = nodeScreenBox(node);
      within(bounds.left, box.left);
      within(box.right, bounds.left + bounds.width);
      within(bounds.top, box.top);
      within(box.bottom, bounds.top + bounds.height);
    }
  });

  it("frames a panel's foot, not just its face", () => {
    // The bug this guards: bounds measured to the bottom of the card cut the
    // strut and deck plate off the front-most panels, because their feet
    // project *below* their anchors.
    const bounds = canvasWorldBounds();
    const frontmost = CANVAS_NODES.reduce((lowest, node) =>
      nodeScreenBox(node).bottom > nodeScreenBox(lowest).bottom ? node : lowest,
    );
    const foot = nodeScreenBox(frontmost).bottom;
    expect(foot).toBeGreaterThan(nodeCardBox(frontmost).bottom);
    expect(bounds.top + bounds.height).toBeGreaterThanOrEqual(foot);
  });

  it("still fills most of a desktop stage", () => {
    // The other regression: bounds that declare more room than the scene
    // occupies make `fitView` zoom out, which is what shrank an 11px label to
    // 7px. Framing the feet costs some of that back, so this is a floor rather
    // than a target — it is the tall struts on the far arc that set it.
    const bounds = canvasWorldBounds();
    expect(fitBounds({ width: 1920, height: 938 }, bounds, 32).z).toBeGreaterThan(0.85);
  });

  it("keeps the pod inside the frame even though it stands at the origin", () => {
    const bounds = canvasWorldBounds([]);
    expect(bounds.width).toBeGreaterThan(0);
    expect(bounds.height).toBeGreaterThan(0);
  });
});

describe("node state", () => {
  it("marks exactly the node whose page is open", () => {
    const active = CANVAS_NODES.filter((node) => isNodeActive(node, PAGE.SBOM));
    expect(active).toHaveLength(1);
    expect(activeNode(PAGE.SBOM)?.label).toBe("SBOM");
  });

  it("has no active node while the hub canvas itself is showing", () => {
    expect(activeNode(PAGE.CANVAS)).toBeUndefined();
  });

  // Doneness travels with the REE, not with the session that produced it: no
  // badge is set here, which is exactly the state a reloaded tab starts in.
  it("reads an executed node as done from the REE's own audit", () => {
    const ree = patchReeEditorViewModel(createEmptyReeEditorViewModel(), {
      audit: { runtime: "current" },
    });
    expect(isNodeDone(nodeFor(PAGE.BUILD), ree, {})).toBe(true);
    expect(isNodeStale(nodeFor(PAGE.BUILD), ree)).toBe(false);
  });

  it("reads a stale node as not done, and names it stale", () => {
    const ree = patchReeEditorViewModel(createEmptyReeEditorViewModel(), {
      audit: { runtime: "stale" },
    });
    expect(isNodeDone(nodeFor(PAGE.BUILD), ree, {})).toBe(false);
    expect(isNodeStale(nodeFor(PAGE.BUILD), ree)).toBe(true);
  });

  it("has no staleness to report for a node with no receipt behind it", () => {
    const ree = createEmptyReeEditorViewModel();
    expect(isNodeStale(nodeFor(PAGE.METADATA), ree)).toBe(false);
    expect(isNodeStale(nodeFor(PAGE.SEAL), ree)).toBe(false);
  });
});

describe("nodeSummary", () => {
  it("shows nothing but empty rows for a fresh REE", () => {
    // Two nodes report a standing rather than an absence, and always have a
    // value: Evaluate scores every axis from zero, and Seal reads "draft".
    const alwaysPopulated: string[] = [PAGE.EVALUATE, PAGE.SEAL];
    for (const node of CANVAS_NODES) {
      if (alwaysPopulated.includes(node.key)) continue;
      for (const row of nodeSummary(node, createEmptyReeEditorViewModel())) {
        expect(row.value).toBeNull();
      }
    }
  });

  describe("Source", () => {
    const repo: SourceRepoMetadata = {
      name: "python-hello-world.tar.gz",
      origin: "https://github.com/example/hello",
      acquiredBy: "upload",
      sourceType: "tarball",
      swhid: "swh:1:dir:abc123",
      sizeBytes: 4096,
      sizeLabel: "4.0 KB",
    };

    it("falls back to the declared origin before any source is in the workspace", () => {
      const summary = summaryOf(PAGE.SOURCE, {
        spec: { originUrl: "https://github.com/example/hello" },
      });
      expect(summary.Origin).toBe("github.com");
      expect(summary.SWHID).toBeNull();
    });

    it("ignores backend metadata until the source is actually available", () => {
      // `sourceAvailable` is the gate: stale repo stats must not show through.
      expect(summaryOf(PAGE.SOURCE, { source: { sourceAvailable: false } }, repo).SWHID).toBeNull();
    });

    it("surfaces the backend-computed stats once the source lands", () => {
      const summary = summaryOf(PAGE.SOURCE, { source: { sourceAvailable: true } }, repo);
      expect(summary).toMatchObject({
        Size: "4.0 KB",
        Origin: "github.com",
        SWHID: "swh:1:dir:abc123",
      });
    });

    it("shortens an origin to its host, and survives one that is not a URL", () => {
      const local = { ...repo, origin: "not a url/at all" };
      expect(summaryOf(PAGE.SOURCE, { source: { sourceAvailable: true } }, local).Origin).toBe(
        "not a url",
      );
    });
  });

  it("counts only experiments that have a run script", () => {
    const experiments = [
      { runScript: "python main.py" },
      { runScript: "   " },
      { runScript: "" },
    ] as never;
    expect(summaryOf(PAGE.EXPERIMENTS, { spec: { experiments } })["Run scripts"]).toBe("1 defined");
  });

  it("treats a skipped runtime as no runtime", () => {
    // "__skipped__" is a real recorded choice, not a built image.
    expect(summaryOf(PAGE.BUILD, { spec: { runtime: "__skipped__" } }).Runtime).toBeNull();
    expect(summaryOf(PAGE.BUILD, { spec: { runtime: "runtime.tar" } }).Runtime).toBe("image ready");
  });

  it("reports the seal as the draft/sealed distinction", () => {
    expect(summaryOf(PAGE.SEAL).State).toBe("draft");
    expect(summaryOf(PAGE.SEAL, { artifact: { sealedAt: "2026-07-30T12:00:00Z" } }).State).toBe(
      "sealed",
    );
  });

  it("always shows all three reproducibility axes, scored or not", () => {
    const fresh = summaryOf(PAGE.EVALUATE);
    expect(fresh).toEqual({
      Dependencies: "None",
      Environment: "None",
      Machine: "None",
      "Detected deps": null,
    });

    const scored = summaryOf(PAGE.EVALUATE, {
      evaluation: { dependencyLevel: 3, environmentLevel: 1 },
    });
    expect(scored).toMatchObject({ Dependencies: "Locked", Environment: "Container" });
  });
});

describe("nodeOverview", () => {
  const files = [
    {
      id: "overlay",
      name: "overlay",
      type: "folder" as const,
      children: [
        {
          id: "build",
          name: "build.sh",
          type: "file" as const,
          content: "#!/bin/sh\nset -eu\ndocker build .\necho done",
        },
        {
          id: "smoke",
          name: "smoke.sh",
          type: "file" as const,
          content: "python smoke.py\necho ignored",
        },
      ],
    },
  ];

  it("previews the saved build script and its receipt evidence", () => {
    const [receipt] = parseAuthorReceipts({
      build: {
        operation: "build_runtime",
        run_id: "run-build",
        duration_ms: 12_400,
        recorded_at: "2026-08-26T10:00:00Z",
        build_runtime_script_digest: "sha256:0123456789abcdef0123456789abcdef",
      },
    });
    const overview = nodeOverview(nodeFor(PAGE.BUILD), createEmptyReeEditorViewModel(), undefined, {
      workspaceFiles: files,
      receipts: [receipt],
      buildScriptPath: "overlay/build.sh",
    });

    expect(overview.scripts[0]).toMatchObject({
      label: "BUILD SCRIPT",
      path: "overlay/build.sh",
      available: true,
      lines: ["#!/bin/sh", "set -eu", "docker build ."],
    });
    expect(overview.receipt).toMatchObject({
      label: "receipt recorded",
      duration: "12.400s",
      scriptDigest: "sha256:012345678…",
    });
  });

  it("builds a bounded-preview-ready experiment roster and reports receipt coverage", () => {
    const experiments = [
      {
        ...createEmptyReeExperiment(),
        name: "smoke",
        runScript: "overlay/smoke.sh",
      },
      { ...createEmptyReeExperiment(), name: "benchmark", runScript: "overlay/missing.sh" },
      { ...createEmptyReeExperiment(), name: "training" },
    ];
    const receipts = parseAuthorReceipts({
      experiments: {
        smoke: {
          operation: "run_experiment",
          experiment_name: "smoke",
          run_id: "run-smoke",
          duration_ms: 900,
          recorded_at: "2026-08-26T10:00:00Z",
          run_script_digest: "sha256:smoke",
        },
      },
    });
    const ree = patchReeEditorViewModel(createEmptyReeEditorViewModel(), {
      spec: { experiments },
    });
    const overview = nodeOverview(nodeFor(PAGE.EXPERIMENTS), ree, undefined, {
      workspaceFiles: files,
      receipts,
    });

    expect(overview.scripts).toHaveLength(3);
    expect(overview.scripts[0]).toMatchObject({
      label: "smoke",
      available: true,
      lines: ["python smoke.py"],
    });
    expect(overview.scripts[1].available).toBe(false);
    expect(overview.scripts[2].path).toBe("");
    expect(overview.receipt?.label).toBe("1/3 receipts");
  });
});
