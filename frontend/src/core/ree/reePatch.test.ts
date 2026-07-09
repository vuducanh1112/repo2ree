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
      catalog_metadata: {
        ...createEmptyReeSpec().catalog_metadata,
        description: "Demo REE",
        keywords: ["reproducibility"],
      },
      origin_url: "https://example.org/repo.git",
      source_type: "git" as const,
      runtime: "runtime.tar.gz",
      sbom: "sbom.json",
      swhid: "swh:1:dir:test",
      experiments: [
        {
          name: "benchmark",
          description: "Measure throughput",
          run_script: "ree/experiments/benchmark.sh",
          verify_script: "ree/experiments/benchmark.verify.sh",
          output_paths: ["results/benchmark.json"],
          runtime_estimate: "15-20 min",
          resource_estimates: {
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

    // The resolved commit is backend-owned, so it is never serialized into the
    // patch — a stale/blank local copy must not clobber what acquisition recorded.
    expect(patch).not.toHaveProperty("revision");
    expect(patch).toEqual({
      ...reeSpec,
      resolvedRevision: undefined,
      zenodo_doi: "",
      dataverse_doi: "",
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
      origin_url: "",
    });
  });
});
