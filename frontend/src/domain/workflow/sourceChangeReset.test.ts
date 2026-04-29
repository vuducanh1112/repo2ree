import { describe, expect, it } from "vitest";
import { initialServiceParams } from "../../constants/services";
import type { ExplorerSourceResetInput } from "./sourceChangeReset";
import { computeExplorerSourceChangeReset } from "./sourceChangeReset";

function buildExplorerState(): ExplorerSourceResetInput {
  return {
    ree: {
      name: "demo",
      origin_url: "https://example.org/repo.git",
      source_type: "git",
      runtime: "runtime.tar.gz",
      build_runtime_script: "build.sh",
      activation_script: "activate.sh",
      sbom: "sbom.json",
      swhid: "swh:1:dir:abc",
      repro_level: "L3",
      detected_dependencies: "3 dependencies",
      hardware_description: {
        cpus: {},
        gpus: {},
        memory: {},
        storage: {},
        network: {},
        extra_info: {},
      },
      _evalLevel: 3,
      _sourceAvailable: true,
      _sourceAcquiredBy: "download",
      _uploadedArchive: "archive.tar.gz",
      _sourceSnapshotArchive: "snapshot.tar.gz",
      _sourceSnapshotCapturedAt: "2026-01-01T00:00:00Z",
      _runtimeIncluded: true,
    },
  };
}

describe("computeExplorerSourceChangeReset", () => {
  it("clears workflow artifacts while preserving unrelated explorer state", () => {
    const explorer = buildExplorerState();
    const nextServiceParams = initialServiceParams();

    const reset = computeExplorerSourceChangeReset(explorer, nextServiceParams);

    expect(reset.serviceParams).toEqual(nextServiceParams);
    expect(reset.badges).toEqual({});
    expect(reset.virtualFiles).toEqual([]);
    expect(reset.ree.runtime).toBe("");
    expect(reset.ree.origin_url).toBe("");
    expect(reset.ree._evalLevel).toBe(0);
  });
});
