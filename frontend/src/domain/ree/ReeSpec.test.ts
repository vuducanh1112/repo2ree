import { describe, expect, it } from "vitest";
import type { ReeViewState } from "./ReeViewState";

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

describe("Ree view state shape", () => {
  it("contains both spec and workflow-derived fields", () => {
    const ree = buildReeDraft();
    expect(ree.name).toBe("demo");
    expect(ree.sourceAvailable).toBe(true);
    expect(ree.runtimeIncluded).toBe(true);
    expect(ree.evalLevel).toBe(4);
  });
});
