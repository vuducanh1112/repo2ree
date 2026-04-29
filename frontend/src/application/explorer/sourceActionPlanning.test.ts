import { describe, expect, it } from "vitest";
import type { FileTreeNode, Ree } from "../../types";
import {
  planClearedSourceStateResult,
  planDownloadedSourceState,
  planSourceDownloadAction,
  planSourceUploadAction,
  planSourceWorkflowFailure,
  planUploadedSourceState,
} from "./sourceActionPlanning";

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

describe("sourceActionPlanning", () => {
  it("builds a normalized download workflow request", () => {
    const result = planSourceDownloadAction(buildRee(), "git", " https://example.org/repo.git ");

    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.value.normalizedSourceUrl).toBe("https://example.org/repo.git");
      expect(result.value.resetRequest).toEqual({
        mode: "download",
        source: "https://example.org/repo.git",
        sourceType: "git",
      });
    }
  });

  it("builds an upload workflow request", () => {
    const result = planSourceUploadAction(buildRee(), "source.tar.gz", "abc123");

    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.value.runParams).toEqual({
        mode: "upload",
        archiveName: "source.tar.gz",
        archiveContentBase64: "abc123",
      });
    }
  });

  it("formats workflow failures for the shell", () => {
    expect(planSourceWorkflowFailure("failed")).toEqual({
      ok: false,
      error: "Source failed",
    });
  });

  it("builds normalized download success state", () => {
    const workspaceFiles: FileTreeNode[] = [
      {
        id: "1",
        name: "repo",
        type: "folder",
        children: [{ id: "2", name: "README.md", type: "file" }],
      },
    ];

    const result = planDownloadedSourceState({
      ree: buildRee(),
      originType: "git",
      normalizedSourceUrl: "https://example.org/org/repo.git",
      workspaceFiles,
      timestamp: "2026-01-01T00:00:00Z",
    });

    expect(result.snapshotArchiveName).toBe("repo-original.tar.gz");
    expect(result.actionState).toBe("done");
    expect(result.badge).toBe(true);
    expect(result.ree._sourceAcquiredBy).toBe("download");
    expect(result.snapshotFiles).not.toBe(workspaceFiles);
    expect(result.snapshotFiles[0]).not.toBe(workspaceFiles[0]);
  });

  it("builds normalized upload success state", () => {
    const workspaceFiles: FileTreeNode[] = [{ id: "1", name: "README.md", type: "file" }];

    const result = planUploadedSourceState({
      ree: buildRee(),
      archiveName: "source.tgz",
      workspaceFiles,
      timestamp: "2026-01-01T00:00:00Z",
    });

    expect(result.snapshotArchiveName).toBe("source.tar.gz");
    expect(result.ree._sourceAcquiredBy).toBe("upload");
  });

  it("builds normalized clear state", () => {
    const result = planClearedSourceStateResult({
      ...buildRee(),
      origin_url: "https://example.org/repo.git",
      _sourceAvailable: true,
      _sourceAcquiredBy: "download",
    });

    expect(result.ree.origin_url).toBe("");
    expect(result.snapshotFiles).toEqual([]);
    expect(result.snapshotArchiveName).toBe("");
  });
});
