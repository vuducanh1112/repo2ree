import { describe, expect, it } from "vitest";

function buildReeDraft() {
  return {
    name: "demo",
    originUrl: "https://example.org/repo.git",
    sourceType: "git",
    runtime: "runtime.tar.gz",
    activation_script: "activate_runtime.sh",
    sbom: "artifacts/sbom.json",
    swhid: "swh:1:dir:test",
    zenodoDoi: "10.1234/example",
    dataverseDoi: "doi:10.5678/example",
    detectedDependencies: "4 dependencies",
    hardwareDescription: {
      cpus: {},
      gpus: {},
      memory: {},
      storage: {},
      network: {},
      extraInfo: {},
    },
    sourceAvailable: true,
    sourceIncluded: true,
    sourceAcquiredBy: "download",
    uploadedArchive: "repo.tar.gz",
    sourceSnapshotArchive: "repo-original.tar.gz",
    sourceSnapshotCapturedAt: "2026-01-01T00:00:00Z",
    runtimeIncluded: true,
    sealedAt: "2026-01-02T00:00:00Z",
    sealHash: "sha256:test",
    dependencyLevel: 3,
  };
}

describe("Ree draft shape", () => {
  it("contains both spec and step-derived fields", () => {
    const ree = buildReeDraft();
    expect(ree.name).toBe("demo");
    expect(ree.sourceAvailable).toBe(true);
    expect(ree.runtimeIncluded).toBe(true);
    expect(ree.dependencyLevel).toBe(3);
  });
});
