import { PAGE } from "@core/app-shell/pages";
import {
  activeNode,
  CANVAS_NODES,
  EXPLODE_LAYERS,
  isNodeActive,
  isNodeLocked,
  nodeProjection,
  nodeSummary,
} from "@core/canvas/canvasNodes";
import { createEmptyReeEditorViewModel } from "@core/ree-editor/reeEditorViewModel";
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
  ree: Partial<ReturnType<typeof createEmptyReeEditorViewModel>> = {},
  sourceRepo?: SourceRepoMetadata,
): Record<string, string | null> {
  const rows = nodeSummary(
    nodeFor(page),
    { ...createEmptyReeEditorViewModel(), ...ree },
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
      PAGE.EXPERIMENTS,
      PAGE.EVALUATE,
      PAGE.BUILD,
      PAGE.SBOM,
      PAGE.ACTIVATION,
      PAGE.ARCHIVE,
      PAGE.SEAL,
    ]);
  });

  it("splits declarations left of the pod and evidence right of it", () => {
    for (const node of CANVAS_NODES) {
      if (node.kind === "declare") expect(node.x).toBeLessThan(0);
      if (node.kind === "evidence") expect(node.x).toBeGreaterThan(0);
    }
  });

  it("assigns every node to a shell that the exploded view has a column for", () => {
    const columns = new Set(EXPLODE_LAYERS.map((layer) => layer.zone));
    for (const node of CANVAS_NODES) expect(columns.has(node.zone)).toBe(true);
  });
});

describe("nodeProjection", () => {
  it("is the identity in the assembled view", () => {
    for (const node of CANVAS_NODES) {
      expect(nodeProjection(node, false)).toEqual({ dx: 0, dy: 0, scale: 1 });
    }
  });

  it("shifts a node into its own shell's column when decomposed", () => {
    const inner = EXPLODE_LAYERS.find((layer) => layer.zone === "inner");
    const sbom = nodeFor(PAGE.SBOM);
    expect(nodeProjection(sbom, true).dx).toBe(inner?.cx);
  });

  it("keeps every panel full size — only the pod shrinks per column", () => {
    for (const node of CANVAS_NODES) {
      expect(nodeProjection(node, true).scale).toBe(1);
      expect(nodeProjection(node, true).dy).toBe(0);
    }
  });

  it("honours xExploded, which moves Source and Build across the pod", () => {
    const build = nodeFor(PAGE.BUILD);
    const inner = EXPLODE_LAYERS.find((layer) => layer.zone === "inner");
    // Build sits right of the pod assembled and left of it decomposed, so the
    // shift is the column offset plus the swing across.
    expect(build.xExploded).toBeDefined();
    expect(nodeProjection(build, true).dx).toBe(
      (inner?.cx ?? 0) + ((build.xExploded ?? 0) - build.x),
    );
  });
});

describe("node state", () => {
  it("locks every node until the workbench is provisioned", () => {
    for (const node of CANVAS_NODES) {
      expect(isNodeLocked(node, false)).toBe(true);
      expect(isNodeLocked(node, true)).toBe(false);
    }
  });

  it("marks exactly the node whose page is open", () => {
    const active = CANVAS_NODES.filter((node) => isNodeActive(node, PAGE.SBOM));
    expect(active).toHaveLength(1);
    expect(activeNode(PAGE.SBOM)?.label).toBe("SBOM");
  });

  it("has no active node while the hub canvas itself is showing", () => {
    expect(activeNode(PAGE.CANVAS)).toBeUndefined();
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
      const summary = summaryOf(PAGE.SOURCE, { originUrl: "https://github.com/example/hello" });
      expect(summary.Origin).toBe("github.com");
      expect(summary.Name).toBeNull();
      expect(summary.SWHID).toBeNull();
    });

    it("ignores backend metadata until the source is actually available", () => {
      // `sourceAvailable` is the gate: stale repo stats must not show through.
      expect(summaryOf(PAGE.SOURCE, { sourceAvailable: false }, repo).Name).toBeNull();
    });

    it("surfaces the backend-computed stats once the source lands", () => {
      const summary = summaryOf(PAGE.SOURCE, { sourceAvailable: true }, repo);
      expect(summary).toMatchObject({
        Name: "python-hello-world.tar.gz",
        Size: "4.0 KB",
        Origin: "github.com",
        SWHID: "swh:1:dir:abc123",
      });
    });

    it("shortens an origin to its host, and survives one that is not a URL", () => {
      const local = { ...repo, origin: "not a url/at all" };
      expect(summaryOf(PAGE.SOURCE, { sourceAvailable: true }, local).Origin).toBe("not a url");
    });
  });

  it("counts only experiments that have a run script", () => {
    const experiments = [
      { runScript: "python main.py" },
      { runScript: "   " },
      { runScript: "" },
    ] as never;
    expect(summaryOf(PAGE.EXPERIMENTS, { experiments })["Run scripts"]).toBe("1 defined");
  });

  it("treats a skipped runtime as no runtime", () => {
    // "__skipped__" is a real recorded choice, not a built image.
    expect(summaryOf(PAGE.BUILD, { runtime: "__skipped__" }).Runtime).toBeNull();
    expect(summaryOf(PAGE.BUILD, { runtime: "runtime.tar" }).Runtime).toBe("image ready");
  });

  it("reports the seal as the draft/sealed distinction", () => {
    expect(summaryOf(PAGE.SEAL).State).toBe("draft");
    expect(summaryOf(PAGE.SEAL, { sealedAt: "2026-07-30T12:00:00Z" }).State).toBe("sealed");
  });

  it("always shows all three reproducibility axes, scored or not", () => {
    const fresh = summaryOf(PAGE.EVALUATE);
    expect(fresh).toEqual({ Dependencies: "None", Environment: "None", Machine: "None" });

    const scored = summaryOf(PAGE.EVALUATE, { dependencyLevel: 3, environmentLevel: 1 });
    expect(scored).toMatchObject({ Dependencies: "Locked", Environment: "Container" });
  });
});
