import { describe, expect, it } from "vitest";
import type { FileTreeNode, Ree } from "../../types";
import {
  planClearedSourceState,
  planDownloadedSourceSuccess,
  planSourceDownload,
  planSourceUpload,
  planUploadedSourceSuccess,
} from "./sourcePlanning";

function buildRee(): Ree {
  return {
    name: "demo",
    origin_url: "",
    source_type: "",
    runtime: "",
    build_runtime_script: "",
    activation_script: "",
    sbom: "",
    swhid: "",
    hardware_description: {
      cpus: {},
      gpus: {},
      memory: {},
      storage: {},
      network: {},
      extra_info: {},
    },
  };
}

describe("sourcePlanning", () => {
  it("blocks download when source already came from upload", () => {
    const ree = { ...buildRee(), _sourceAvailable: true, _sourceAcquiredBy: "upload" as const };

    const result = planSourceDownload(ree, "git", "https://example.org/repo.git");

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toContain("tarball upload");
    }
  });

  it("normalizes download success state", () => {
    const ree = buildRee();
    const workspaceFiles: FileTreeNode[] = [{ id: "1", name: "README.md", type: "file" }];

    const result = planDownloadedSourceSuccess({
      ree,
      originType: "git",
      normalizedSourceUrl: "https://example.org/org/repo.git",
      workspaceFiles,
      timestamp: "2026-01-01T00:00:00Z",
    });

    expect(result.snapshotArchiveName).toBe("repo-original.tar.gz");
    expect(result.ree._sourceAvailable).toBe(true);
    expect(result.ree._sourceAcquiredBy).toBe("download");
  });

  it("blocks upload when source already came from download", () => {
    const ree = { ...buildRee(), _sourceAvailable: true, _sourceAcquiredBy: "download" as const };

    const result = planSourceUpload(ree);

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toContain("origin download");
    }
  });

  it("normalizes upload success state", () => {
    const ree = buildRee();
    const workspaceFiles: FileTreeNode[] = [{ id: "1", name: "README.md", type: "file" }];

    const result = planUploadedSourceSuccess({
      ree,
      archiveName: "source.tgz",
      workspaceFiles,
      timestamp: "2026-01-01T00:00:00Z",
    });

    expect(result.snapshotArchiveName).toBe("source.tar.gz");
    expect(result.ree._sourceIncluded).toBe(true);
    expect(result.ree._sourceAcquiredBy).toBe("upload");
  });

  it("clears source-specific ree fields", () => {
    const ree: Ree = {
      ...buildRee(),
      origin_url: "https://example.org/repo.git",
      _sourceAvailable: true,
      _sourceAcquiredBy: "download",
      _uploadedArchive: "source.tar.gz",
      _sourceSnapshotArchive: "repo-original.tar.gz",
      _sourceSnapshotCapturedAt: "2026-01-01T00:00:00Z",
    };

    const result = planClearedSourceState(ree);

    expect(result.origin_url).toBe("");
    expect(result._sourceAvailable).toBe(false);
    expect(result._sourceAcquiredBy).toBeUndefined();
    expect(result._sourceSnapshotArchive).toBe("");
  });
});
