/* biome-ignore-all lint/style/useNamingConvention: receipt fixtures intentionally use wire field names */
import { PAGE } from "@core/app-shell/pages";
import {
  activeNode,
  CANVAS_NODES,
  isNodeActive,
  isNodeLocked,
  nodeOverview,
  nodeSummary,
} from "@core/canvas/canvasNodes";
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

  it("lifts every assembled panel above its floor anchor", () => {
    for (const node of CANVAS_NODES) expect(node.standHeight).toBeGreaterThan(0);
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
      const summary = summaryOf(PAGE.SOURCE, {
        spec: { originUrl: "https://github.com/example/hello" },
      });
      expect(summary.Origin).toBe("github.com");
      expect(summary.Name).toBeNull();
      expect(summary.SWHID).toBeNull();
    });

    it("ignores backend metadata until the source is actually available", () => {
      // `sourceAvailable` is the gate: stale repo stats must not show through.
      expect(summaryOf(PAGE.SOURCE, { source: { sourceAvailable: false } }, repo).Name).toBeNull();
    });

    it("surfaces the backend-computed stats once the source lands", () => {
      const summary = summaryOf(PAGE.SOURCE, { source: { sourceAvailable: true } }, repo);
      expect(summary).toMatchObject({
        Name: "python-hello-world.tar.gz",
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
    expect(fresh).toEqual({ Dependencies: "None", Environment: "None", Machine: "None" });

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
