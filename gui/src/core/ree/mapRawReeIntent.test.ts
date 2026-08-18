import { describe, expect, it } from "vitest";
import { mapRawReeIntentToSlices } from "./mapRawReeIntent";

describe("mapRawReeIntentToSlices", () => {
  it("hydrates experiment estimates from persisted intent", () => {
    const mapped = mapRawReeIntentToSlices({
      reeIntent: {
        experiments: [
          {
            name: "benchmark",
            description: "Measure throughput",
            run_script: "ree-scripts/experiments/benchmark.sh",
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
      },
      fallbackName: "demo",
    });

    expect(mapped.reeSpec.experiments).toEqual([
      {
        name: "benchmark",
        description: "Measure throughput",
        runScript: "ree-scripts/experiments/benchmark.sh",
        verifyScript: "",
        outputPaths: [],
        runtimeEstimate: "15-20 min",
        resourceEstimates: {
          cpu: "8 vCPU",
          memory: "16 GB",
          gpu: "1x A10",
          storage: "5 GB scratch",
          network: "offline",
        },
      },
    ]);
  });

  it("backfills missing experiment estimates with stable defaults", () => {
    const mapped = mapRawReeIntentToSlices({
      reeIntent: {
        experiments: [{ name: "smoke", run_script: "ree-scripts/experiments/smoke.sh" }],
      },
      fallbackName: "demo",
    });

    expect(mapped.reeSpec.experiments).toEqual([
      {
        name: "smoke",
        description: "",
        runScript: "ree-scripts/experiments/smoke.sh",
        verifyScript: "",
        outputPaths: [],
        runtimeEstimate: "",
        resourceEstimates: {
          cpu: "",
          memory: "",
          gpu: "",
          storage: "",
          network: "",
        },
      },
    ]);
  });

  it("maps the activation run script from persisted intent", () => {
    const mapped = mapRawReeIntentToSlices({
      reeIntent: {
        activation: { run_script: "ree/custom-activation.sh" },
      },
      fallbackName: "demo",
    });

    expect(mapped.reeSpec.activation.runScript).toBe("ree/custom-activation.sh");
  });

  it("keeps the activation run script empty when not present in intent", () => {
    // The reserved path is backend-owned: intents arrive with it settled, and
    // an empty local value is normalized server-side on the next patch.
    const mapped = mapRawReeIntentToSlices({ reeIntent: {}, fallbackName: "demo" });

    expect(mapped.reeSpec.activation.runScript).toBe("");
  });

  it("reads source_included and runtime_included from session", () => {
    const mapped = mapRawReeIntentToSlices({
      reeIntent: {},
      reeSession: { source_available: true, source_included: true, runtime_included: false },
      fallbackName: "demo",
    });

    expect(mapped.workspaceSourceState.sourceIncluded).toBe(true);
    expect(mapped.artifactStatus.runtimeIncluded).toBe(false);
    expect(mapped.workspaceSourceState.sourceAvailable).toBe(true);
  });

  it("maps every persisted intent and session field", () => {
    const mapped = mapRawReeIntentToSlices({
      reeIntent: {
        name: "persisted",
        catalog_metadata: {
          description: "description",
          version: "1",
          website: "https://example.test",
          keywords: ["one", 2],
          contributors: [
            {
              identifier: "id",
              name: "name",
              affiliation_name: "lab",
              affiliation_identifier: "ror",
            },
          ],
          corresponding_author_identifier: "id",
        },
        origin_url: "https://example.test/repo",
        source_type: "git",
        revision: "abc",
        runtime: "runtime.tar",
        activation: {
          description: "activate",
          run_script: "run.sh",
          verify_script: "verify.sh",
          output_paths: ["one", "", 2],
          runtime_estimate: "minute",
          resource_estimates: { cpu: 2, memory: "1GB", gpu: 0, storage: 3, network: "fast" },
        },
        sbom: "sbom.json",
        swhid: "swh:1:dir:test",
        hardware_description: {},
        experiments: [null],
      },
      reeSession: {
        source_available: true,
        source_included: true,
        source_acquired_by: "url",
        uploaded_archive: "source.tar",
        source_snapshot_archive: "snapshot.tar",
        source_snapshot_captured_at: "now",
        runtime_included: true,
        sealed_at: "sealed",
        seal_hash: "hash",
        dependency_level: 1,
        environment_level: 2,
        machine_level: 3,
        detected_dependencies: "requirements.txt",
      },
      fallbackName: "fallback",
      fallbackOriginUrl: "fallback-url",
    });

    expect(mapped.reeSpec).toMatchObject({
      name: "persisted",
      originUrl: "https://example.test/repo",
      sourceType: "git",
      resolvedRevision: "abc",
      runtime: "runtime.tar",
      sbom: "sbom.json",
      swhid: "swh:1:dir:test",
      catalogMetadata: {
        keywords: ["one", "2"],
        correspondingAuthorIdentifier: "id",
        contributors: [{ affiliationName: "lab", affiliationIdentifier: "ror" }],
      },
      activation: {
        runScript: "run.sh",
        verifyScript: "verify.sh",
        outputPaths: ["one", "2"],
        resourceEstimates: { cpu: "2", memory: "1GB", gpu: "0", storage: "3", network: "fast" },
      },
    });
    expect(mapped.workspaceSourceState).toMatchObject({
      sourceAcquiredBy: "url",
      uploadedArchive: "source.tar",
      sourceSnapshotArchive: "snapshot.tar",
      sourceSnapshotCapturedAt: "now",
    });
    expect(mapped.artifactStatus).toEqual({
      runtimeIncluded: true,
      sealedAt: "sealed",
      sealHash: "hash",
    });
    expect(mapped.evaluationState).toEqual({
      dependencyLevel: 1,
      environmentLevel: 2,
      machineLevel: 3,
      detectedDependencies: "requirements.txt",
    });
  });

  it("uses fallbacks and defaults for null or malformed slices", () => {
    const mapped = mapRawReeIntentToSlices({
      reeIntent: null,
      reeSession: null,
      fallbackName: "fallback",
      fallbackOriginUrl: "fallback-url",
    });
    expect(mapped.reeSpec.name).toBe("fallback");
    expect(mapped.reeSpec.originUrl).toBe("fallback-url");
    expect(mapped.reeSpec.catalogMetadata).toMatchObject({
      keywords: [],
      contributors: [],
      correspondingAuthorIdentifier: null,
    });
    expect(mapped.reeSpec.experiments).toEqual([]);
    expect(mapped.workspaceSourceState).toEqual({
      sourceAvailable: false,
      sourceIncluded: false,
      sourceAcquiredBy: undefined,
      uploadedArchive: undefined,
      sourceSnapshotArchive: undefined,
      sourceSnapshotCapturedAt: undefined,
    });
    expect(mapped.artifactStatus).toEqual({
      runtimeIncluded: false,
      sealedAt: undefined,
      sealHash: undefined,
    });
  });
});
