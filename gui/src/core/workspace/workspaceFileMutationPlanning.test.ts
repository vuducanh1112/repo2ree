import { describe, expect, it } from "vitest";
import {
  planReeArchiveDownload,
  planWorkspaceFileDownload,
  planWorkspaceFilePersistence,
} from "./workspaceFileMutationPlanning";

describe("workspaceFileMutationPlanning", () => {
  it("plans workspace file persistence at the trimmed path", () => {
    const result = planWorkspaceFilePersistence(" new/name.txt ");

    expect(result.normalizedPath).toBe("new/name.txt");
    expect(result.successMessage).toBe("Saved new/name.txt to workspace");
  });

  it("plans workspace file download names safely", () => {
    const result = planWorkspaceFileDownload("dir/file.txt", "dir\\file.txt");

    expect(result.downloadName).toBe("dir_file.txt");
    expect(result.successMessage).toBe("Downloaded dir_file.txt");
  });

  it("plans ree archive fallback names", () => {
    const result = planReeArchiveDownload("my ree", undefined);

    expect(result.archiveFileName).toBe("my_ree.zip");
    expect(result.successMessage).toBe("Downloaded my_ree.zip");
  });
});
