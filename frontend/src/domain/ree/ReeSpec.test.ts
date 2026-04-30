import { describe, expect, it } from "vitest";
import { type Ree, splitLegacyReeModel, toLegacyReeViewModel } from "./ReeSpec";

function buildLegacyRee(): Ree {
  return {
    name: "demo",
    origin_url: "https://example.org/repo.git",
    source_type: "git",
    runtime: "runtime.tar.gz",
    build_runtime_script: "build_runtime.sh",
    activation_script: "activate_runtime.sh",
    sbom: "sbom.json",
    swhid: "swh:1:dir:test",
    zenodo_doi: "10.1234/example",
    dataverse_doi: "doi:10.5678/example",
    repro_level: "L4",
    detected_dependencies: "4 dependencies",
    hardware_description: {
      cpus: {},
      gpus: {},
      memory: {},
      storage: {},
      network: {},
      extra_info: {},
    },
    _sourceAvailable: true,
    _sourceIncluded: true,
    _sourceAcquiredBy: "download",
    _uploadedArchive: "repo.tar.gz",
    _sourceSnapshotArchive: "repo-original.tar.gz",
    _sourceSnapshotCapturedAt: "2026-01-01T00:00:00Z",
    _runtimeIncluded: true,
    _downloadableFiles: ["runtime.tar.gz", "sbom.json"],
    _sealedAt: "2026-01-02T00:00:00Z",
    _sealHash: "sha256:test",
    _evalLevel: 4,
  };
}

describe("ReeSpec adapters", () => {
  it("separates persisted spec from transient frontend state", () => {
    const split = splitLegacyReeModel(buildLegacyRee());

    expect(split.reeSpec.name).toBe("demo");
    expect("_sourceAvailable" in split.reeSpec).toBe(false);
    expect(split.workspaceSourceState._sourceAvailable).toBe(true);
    expect(split.artifactStatus._runtimeIncluded).toBe(true);
    expect(split.evaluationState._evalLevel).toBe(4);
  });

  it("round-trips split state back into the legacy view model", () => {
    const legacy = buildLegacyRee();

    expect(toLegacyReeViewModel(splitLegacyReeModel(legacy))).toEqual(legacy);
  });
});
