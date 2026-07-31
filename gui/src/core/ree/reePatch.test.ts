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

    // Source identity is backend-owned, so it is never serialized into the
    // patch — a stale/blank local copy must not clobber what acquisition recorded.
    expect(patch).not.toHaveProperty("revision");
    expect(patch).not.toHaveProperty("resolvedRevision");
    expect(patch).not.toHaveProperty("swhid");
    // The patch is the backend's wire format: snake_case keys, camelCase gone.
    expect(patch).toEqual({
      name: "demo",
      catalog_metadata: {
        description: "Demo REE",
        version: "",
        website: "",
        keywords: ["reproducibility"],
        contributors: [],
        corresponding_author_identifier: null,
      },
      origin_url: "https://example.org/repo.git",
      source_type: "git",
      runtime: "runtime.tar.gz",
      activation: {
        description: "",
        // Empty is safe on the wire: the backend normalizes it back to the
        // reserved activation path.
        run_script: "",
        verify_script: "",
        output_paths: [],
        runtime_estimate: "",
        resource_estimates: { cpu: "", memory: "", gpu: "", storage: "", network: "" },
      },
      sbom: "artifacts/sbom.json",
      experiments: [
        {
          name: "benchmark",
          description: "Measure throughput",
          run_script: "ree-scripts/experiments/benchmark.sh",
          verify_script: "ree-scripts/experiments/benchmark.verify.sh",
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
      hardware_description: {
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
      origin_url: "",
    });
  });
});
