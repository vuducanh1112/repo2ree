import { describe, expect, it } from "vitest";
import type { FileTreeNode } from "../../domain/workspace/FileTree";
import type { ReeEditorViewModel } from "../ree-editor/reeEditorViewModel";
import {
  planClearedSourceStateResult,
  planDownloadedSourceState,
  planSourceDownloadAction,
  planSourceExecutionFailure,
  planSourceUploadAction,
  planUploadedSourceState,
} from "./sourceAcquisitionPlanning";

function buildRee(): ReeEditorViewModel {
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

describe("sourceAcquisitionPlanning", () => {
  it("builds a normalized download execution request", () => {
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

  it("builds an upload execution request", () => {
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

  it("formats execution run failures for the shell", () => {
    expect(planSourceExecutionFailure("failed")).toEqual({
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
    expect(result.reePatch.sourceAcquiredBy).toBe("download");
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
    expect(result.reePatch.sourceAcquiredBy).toBe("upload");
  });

  it("builds normalized clear state", () => {
    const result = planClearedSourceStateResult();

    expect(result.reePatch.origin_url).toBe("");
    expect(result.snapshotFiles).toEqual([]);
    expect(result.snapshotArchiveName).toBe("");
  });
});
