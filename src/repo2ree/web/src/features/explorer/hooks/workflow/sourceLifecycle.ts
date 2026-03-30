import type React from "react";
import { PAGE } from "../../../../constants/pages";
import { initialServiceParams } from "../../../../constants/services";
import type { AppAction } from "../../../../context";
import { explorerActions } from "../../../../context";
import {
  cloneDummyWorkspaceTree,
  createInMemoryDummyWorkspaceService,
  MOCK_FILES,
  makeDummyWorkspaceFromArchiveUpload,
  makeDummyWorkspaceFromOrigin,
} from "../../../../services/dummyWorkspaceService";
import type {
  IWorkspaceService,
  WorkspaceServiceLogEntry,
} from "../../../../services/workspaceService";
import type { FileTreeNode, Ree, ServiceParams, SourceUploadCommit } from "../../../../types";
import { normalizeSnapshotArchiveName, normalizeWorkspacePath } from "../../../../utils";
import type { ShowToast } from "./types";

export const WORKSPACE_ID = "active";

export function upsertWorkspaceFile(
  nodes: FileTreeNode[],
  path: string,
  content: string,
): FileTreeNode[] {
  const normalizedPath = normalizeWorkspacePath(path);
  const name = normalizedPath.split("/").pop() || normalizedPath || "file.txt";
  const updatedFile: FileTreeNode = {
    id: `vf-${normalizedPath || name}`,
    name,
    type: "file",
    tag: PAGE.SOURCE,
    content,
  };
  return [...nodes.filter((node) => !(node.type === "file" && node.name === name)), updatedFile];
}

export function resetWorkflowOnSourceChange(
  dispatch: React.Dispatch<AppAction>,
  showToast: ShowToast,
  options: { silent?: boolean } = {},
): void {
  dispatch(explorerActions.resetWorkflowOnSourceChange(initialServiceParams()));
  if (!options.silent) {
    showToast("Source changed — workflow status and scripts reset", "info");
  }
}

interface CreateWorkspaceServiceArgs {
  ree: Ree;
  virtualFiles: FileTreeNode[];
  serviceParams: ServiceParams;
  dispatch: React.Dispatch<AppAction>;
  executeServiceRun: (
    key: string,
    params?: Record<string, unknown>,
  ) => Promise<WorkspaceServiceLogEntry>;
}

export function createExplorerWorkspaceService({
  ree,
  virtualFiles,
  serviceParams,
  dispatch,
  executeServiceRun,
}: CreateWorkspaceServiceArgs): IWorkspaceService<FileTreeNode> {
  return createInMemoryDummyWorkspaceService<FileTreeNode, Ree["source_type"]>({
    getWorkspaceFiles: () => virtualFiles,
    updateWorkspaceFiles: (virtualFilesUpdate) =>
      dispatch(explorerActions.setVirtualFiles(virtualFilesUpdate)),
    upsertFile: (previous, path, content) => upsertWorkspaceFile(previous, path, content),
    runScript: async (scriptKey: string): Promise<WorkspaceServiceLogEntry> => {
      const params = serviceParams[scriptKey] ?? {};
      return executeServiceRun(scriptKey, params);
    },
    clearWorkspace: () => {
      dispatch(explorerActions.setVirtualFiles([]));
      dispatch(explorerActions.setImmutableSourceSnapshotFiles([]));
      dispatch(explorerActions.setImmutableSourceSnapshotArchiveName(""));
      dispatch(
        explorerActions.setRee((prevRee) => ({
          ...prevRee,
          runtime: "",
          _sourceAvailable: false,
          _sourceAcquiredBy: undefined,
          _runtimeIncluded: false,
          _uploadedArchive: "",
          _sourceSnapshotArchive: "",
          _sourceSnapshotCapturedAt: "",
        })),
      );
    },
    loadWorkspaceFromUpload: (archiveName: string) => {
      const ts = new Date().toISOString();
      const workspaceFiles = makeDummyWorkspaceFromArchiveUpload(
        MOCK_FILES,
        archiveName,
        PAGE.SOURCE,
      );
      const snapshotFiles = cloneDummyWorkspaceTree(workspaceFiles);
      const snapshotArchiveName = normalizeSnapshotArchiveName(archiveName);

      dispatch(explorerActions.setVirtualFiles(workspaceFiles));
      dispatch(explorerActions.setImmutableSourceSnapshotFiles(snapshotFiles));
      dispatch(explorerActions.setImmutableSourceSnapshotArchiveName(snapshotArchiveName));
      dispatch(
        explorerActions.setRee((prevRee) => ({
          ...prevRee,
          _uploadedArchive: archiveName,
          source_type: "",
          _sourceAvailable: true,
          _sourceAcquiredBy: "upload",
          _sourceSnapshotArchive: snapshotArchiveName,
          _sourceSnapshotCapturedAt: ts,
        })),
      );
    },
    loadWorkspaceFromDownload: (sourceUrl: string, sourceType: Ree["source_type"]) => {
      if (!sourceUrl || !sourceType) return;

      const ts = new Date().toISOString();
      const workspaceFiles = makeDummyWorkspaceFromOrigin(
        MOCK_FILES,
        sourceUrl,
        sourceType,
        PAGE.SOURCE,
      );
      const snapshotFiles = cloneDummyWorkspaceTree(workspaceFiles);
      const repoBase =
        (sourceUrl.split("/").filter(Boolean).pop() || "source").replace(
          /\.(git|tar\.gz|tgz|zip)$/i,
          "",
        ) || "source";
      const snapshotArchiveName = normalizeSnapshotArchiveName(`${repoBase}-original.tar.gz`);

      dispatch(explorerActions.setVirtualFiles(workspaceFiles));
      dispatch(explorerActions.setImmutableSourceSnapshotFiles(snapshotFiles));
      dispatch(explorerActions.setImmutableSourceSnapshotArchiveName(snapshotArchiveName));
      dispatch(
        explorerActions.setRee((prevRee) => ({
          ...prevRee,
          origin_url: sourceUrl,
          source_type: sourceType,
          _sourceAvailable: true,
          _sourceAcquiredBy: "download",
          _uploadedArchive: "",
          _sourceSnapshotArchive: snapshotArchiveName,
          _sourceSnapshotCapturedAt: ts,
        })),
      );
    },
    getDefaultSource: () => ree.origin_url,
    getDefaultSourceType: () => ree.source_type || "git",
  });
}

interface CreateSourceActionsArgs {
  ree: Ree;
  workspaceService: IWorkspaceService<FileTreeNode>;
  dispatch: React.Dispatch<AppAction>;
  onSourceChange: (options?: { silent?: boolean }) => void;
  showToast: ShowToast;
}

export function createSourceActions({
  ree,
  workspaceService,
  dispatch,
  onSourceChange,
  showToast,
}: CreateSourceActionsArgs) {
  const handleDownloadSourceFiles = async (originType: Ree["source_type"]) => {
    if (ree._sourceAvailable && ree._sourceAcquiredBy === "upload") {
      showToast(
        "Source already provided via tarball upload. Change source to switch method.",
        "error",
      );
      return;
    }
    if (!ree.origin_url || !originType) {
      showToast("Set origin URL and origin type first", "error");
      return;
    }
    onSourceChange({ silent: true });
    dispatch(
      explorerActions.setActionStates((prevStates) => ({ ...prevStates, source: "loading" })),
    );
    await new Promise((resolve) => setTimeout(resolve, 1400));
    dispatch(explorerActions.setActionStates((prevStates) => ({ ...prevStates, source: "done" })));
    dispatch(explorerActions.setBadges((prevBadges) => ({ ...prevBadges, source: true })));
    const ts = new Date().toISOString();
    dispatch(
      explorerActions.setTimestamps((prevTimestamps) => ({ ...prevTimestamps, source: ts })),
    );
    await workspaceService.resetWorkspace(
      WORKSPACE_ID,
      JSON.stringify({ mode: "download", source: ree.origin_url, sourceType: originType }),
    );
    showToast(
      originType === "tarball"
        ? "Tarball downloaded and extracted into workspace"
        : "Source files downloaded into workspace",
      "success",
    );
  };

  const handleWorkspaceUpload = (payload: SourceUploadCommit) => {
    if (ree._sourceAvailable && ree._sourceAcquiredBy === "download") {
      showToast(
        "Source already provided via origin download. Change source to switch method.",
        "error",
      );
      return;
    }
    onSourceChange({ silent: true });
    const ts = new Date().toISOString();

    const archiveName = payload.archiveName || "source.tar.gz";
    void workspaceService.resetWorkspace(
      WORKSPACE_ID,
      JSON.stringify({ mode: "upload", archiveName }),
    );
    dispatch(explorerActions.setBadges((prevBadges) => ({ ...prevBadges, source: true })));
    dispatch(
      explorerActions.setTimestamps((prevTimestamps) => ({ ...prevTimestamps, source: ts })),
    );
    showToast("Archive extracted into workspace", "success");
  };

  const handleRemoveWorkspaceSource = () => {
    onSourceChange({ silent: true });
    void workspaceService.resetWorkspace(WORKSPACE_ID, JSON.stringify({ mode: "clear" }));
    showToast("Source files removed from workspace — choose download or upload again", "info");
  };

  return {
    handleDownloadSourceFiles,
    handleWorkspaceUpload,
    handleRemoveWorkspaceSource,
  };
}
