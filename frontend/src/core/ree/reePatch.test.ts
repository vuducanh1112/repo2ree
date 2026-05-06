import { describe, expect, it } from "vitest";
import type { ArtifactStatus } from "../artifact/ArtifactStatus";
import type { EvaluationState } from "../review/EvaluationState";
import type { WorkspaceSourceState } from "../workspace/WorkspaceSourceState";
import { createEmptyReeSpec } from "./ReeSpec";
import { toReePatchFromSlices } from "./reePatch";

describe("toReePatchFromSlices", () => {
  it("serializes persisted and transient slices into the legacy patch contract", () => {
    const reeSpec = {
      ...createEmptyReeSpec(),
      name: "demo",
      origin_url: "https://example.org/repo.git",
      source_type: "git" as const,
      runtime: "runtime.tar.gz",
      sbom: "sbom.json",
      swhid: "swh:1:dir:test",
      repro_level: "L4",
      detected_dependencies: "4 dependencies",
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
      downloadableFiles: ["runtime.tar.gz", "sbom.json"],
      sealedAt: "2026-01-02T00:00:00Z",
      sealHash: "sha256:test",
    };
    const evaluationState: EvaluationState = {
      evalLevel: 4,
    };

    expect(
      toReePatchFromSlices({
        reeSpec,
        workspaceSourceState,
        artifactStatus,
        evaluationState,
      }),
    ).toEqual({
      ...reeSpec,
      _sealedAt: "2026-01-02T00:00:00Z",
      _sealHash: "sha256:test",
      _evalLevel: 4,
      _sourceIncluded: true,
      _sourceAvailable: true,
      _sourceAcquiredBy: "download",
      _uploadedArchive: "repo.tar.gz",
      _sourceSnapshotArchive: "repo-original.tar.gz",
      _sourceSnapshotCapturedAt: "2026-01-01T00:00:00Z",
      _runtimeIncluded: true,
      _downloadableFiles: ["runtime.tar.gz", "sbom.json"],
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
      _evalLevel: 0,
      _sourceIncluded: false,
      _sourceAvailable: false,
      _sourceAcquiredBy: "",
      _runtimeIncluded: false,
      _downloadableFiles: [],
    });
  });
});
