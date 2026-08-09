import { describe, expect, it } from "vitest";
import type { ArtifactStatus } from "../artifact/ArtifactStatus";
import type { EvaluationState } from "../evaluate/EvaluationState";
import type { WorkspaceSourceState } from "../workspace/WorkspaceSourceState";
import { createEmptyReeSpec } from "./ReeSpec";
import { toReePatchFromSlices } from "./reePatch";

describe("toReePatchFromSlices", () => {
  it("serializes user-editable REE draft fields without backend-managed state", () => {
    const reeSpec = {
      ...createEmptyReeSpec(),
      name: "demo",
      catalogMetadata: {
        ...createEmptyReeSpec().catalogMetadata,
        description: "Demo REE",
        keywords: ["reproducibility"],
      },
      originUrl: "https://example.org/repo.git",
      sourceType: "git" as const,
      runtime: "runtime.tar.gz",
      sbom: "artifacts/sbom.json",
      swhid: "swh:1:dir:test",
      experiments: [
        {
          name: "benchmark",
          description: "Measure throughput",
          runScript: "ree-scripts/experiments/benchmark.sh",
          verifyScript: "ree-scripts/experiments/benchmark.verify.sh",
          outputPaths: ["results/benchmark.json"],
          runtimeEstimate: "15-20 min",
          resourceEstimates: {
            cpu: "8 vCPU",
            memory: "16 GB",
            gpu: "1x A10",
            storage: "5 GB scratch",
            network: "offline",
          },
        },
      ],
    };
    const workspaceSourceState: WorkspaceSourceState = {
      sourceAvailable: true,
      sourceIncluded: true,
      sourceAcquiredBy: "download",
      uploadedArchive: "repo.tar.gz",
      sourceSnapshotArchive: "repo-original.tar.gz",
      sourceSnapshotCapturedAt: "2026-01-01T00:00:00Z",
    };
    const artifactStatus: ArtifactStatus = {
      runtimeIncluded: true,
      sealedAt: "2026-01-02T00:00:00Z",
      sealHash: "sha256:test",
    };
    const evaluationState: EvaluationState = {
      dependencyLevel: 3,
    };

    const patch = toReePatchFromSlices({
      reeSpec,
      workspaceSourceState,
      artifactStatus,
      evaluationState,
    });

    // Observed source identity is receipt-owned, so it is never serialized into
    // the definition patch.
    expect(patch).not.toHaveProperty("revision");
    expect(patch).not.toHaveProperty("resolvedRevision");
    expect(patch).not.toHaveProperty("swhid");
    // The patch is the backend's wire format: snake_case keys, camelCase gone.
    expect(patch).toEqual({
      name: "demo",
      catalog: {
        description: "Demo REE",
        version: "",
        website: "",
        keywords: ["reproducibility"],
        contributors: [],
        corresponding_author_identifier: null,
      },
      source: {
        origin_url: "https://example.org/repo.git",
        source_type: "git",
        requested_ref: null,
      },
      build_runtime: { runtime_path: "runtime.tar.gz" },
      experiments: [
        {
          name: "benchmark",
          output_paths: ["results/benchmark.json"],
        },
      ],
      hardware: {
        cpus: {},
        gpus: {},
        memory: {},
        storage: {},
        network: {},
        extra_info: {},
      },
    });
  });

  it("fills missing transient values with stable defaults", () => {
    expect(
      toReePatchFromSlices({
        reeSpec: createEmptyReeSpec(),
        workspaceSourceState: {},
        artifactStatus: {},
        evaluationState: {},
      }),
    ).toMatchObject({
      name: "",
      build_runtime: { runtime_path: null },
    });
  });

  // The patch merges by key, so what it omits it preserves. An upload declares
  // its source server-side; sending `source: null` from an editor that never
  // held that declaration would erase it and strand the acquisition receipt.
  it("omits an unauthored source rather than nulling the one the backend declared", () => {
    const patch = toReePatchFromSlices({
      reeSpec: createEmptyReeSpec(),
      workspaceSourceState: {},
      artifactStatus: {},
      evaluationState: {},
    });
    expect(patch).not.toHaveProperty("source");
  });

  // Clearing the declared runtime path must clear the declaration — but never
  // at the cost of the build recipe, which carries the REE's own build script.
  it("clears an undeclared runtime path without dropping the build recipe", () => {
    const patch = toReePatchFromSlices({
      reeSpec: { ...createEmptyReeSpec(), runtime: "" },
      workspaceSourceState: {},
      artifactStatus: {},
      evaluationState: {},
    });
    expect(patch.build_runtime).toEqual({ runtime_path: null });
  });
});
