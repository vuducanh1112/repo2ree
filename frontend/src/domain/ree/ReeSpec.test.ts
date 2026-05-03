import { describe, expect, it } from "vitest";
import type { ReeViewState } from "./ReeViewState";
import { splitReeViewState, toReeViewState } from "./ReeViewState";

function buildReeDraft(): ReeViewState {
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
    sourceAvailable: true,
    sourceIncluded: true,
    sourceAcquiredBy: "download",
    uploadedArchive: "repo.tar.gz",
    sourceSnapshotArchive: "repo-original.tar.gz",
    sourceSnapshotCapturedAt: "2026-01-01T00:00:00Z",
    runtimeIncluded: true,
    downloadableFiles: ["runtime.tar.gz", "sbom.json"],
    sealedAt: "2026-01-02T00:00:00Z",
    sealHash: "sha256:test",
    evalLevel: 4,
  };
}

describe("Ree draft view model helpers", () => {
  it("separates persisted spec from transient frontend state", () => {
    const split = splitReeViewState(buildReeDraft());

    expect(split.reeSpec.name).toBe("demo");
    expect("sourceAvailable" in split.reeSpec).toBe(false);
    expect(split.workspaceSourceState.sourceAvailable).toBe(true);
    expect(split.workspaceSourceState.sourceSnapshotCapturedAt).toBe("2026-01-01T00:00:00Z");
    expect(split.artifactStatus.runtimeIncluded).toBe(true);
    expect(split.artifactStatus.downloadableFiles).toEqual(["runtime.tar.gz", "sbom.json"]);
    expect(split.evaluationState.evalLevel).toBe(4);
  });

  it("round-trips split state back into the draft view model", () => {
    const ree = buildReeDraft();

    expect(toReeViewState(splitReeViewState(ree))).toEqual(ree);
  });
});
