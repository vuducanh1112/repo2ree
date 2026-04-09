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
import { createRemoteWorkspaceService } from "../../../../services/remoteWorkspaceService";
import type {
  IWorkspaceService,
  WorkspaceServiceLogEntry,
} from "../../../../services/workspaceService";
import { serializeWorkspaceResetPayload } from "../../../../services/workspaceService";
import type { FileTreeNode, Ree, ServiceParams, SourceUploadCommit } from "../../../../types";
import type { GenericServiceParams } from "../../../../types/services";
import { normalizeSnapshotArchiveName, normalizeWorkspacePath } from "../../../../utils";
import { pollWorkflowRun } from "./pollWorkflowRun";
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

export function removeWorkspaceFile(nodes: FileTreeNode[], path: string): FileTreeNode[] {
  const normalizedPath = normalizeWorkspacePath(path);
  const name = normalizedPath.split("/").pop() || normalizedPath || "file.txt";

  const prune = (items: FileTreeNode[]): FileTreeNode[] =>
    items
      .flatMap((node) => {
        if (node.type === "file") {
          return node.name === name ? [] : [node];
        }

        const children = node.children ? prune(node.children) : [];
        if (children.length === 0) {
          return [];
        }

        return [{ ...node, children }];
      })
      .filter(Boolean) as FileTreeNode[];

  return prune(nodes);
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
    params?: GenericServiceParams,
  ) => Promise<WorkspaceServiceLogEntry>;
}

export function createExplorerWorkspaceService({
  ree,
  virtualFiles,
  serviceParams,
  dispatch,
  executeServiceRun,
}: CreateWorkspaceServiceArgs): IWorkspaceService<FileTreeNode> {
  const env = (import.meta as ImportMeta & { env?: Record<string, string | undefined> }).env || {};
  const explicitMode = String(env.VITE_WORKSPACE_SERVICE_MODE || "").toLowerCase();
  const workspaceServiceMode = explicitMode || (env.VITE_API_BASE_URL ? "remote" : "mock");
  if (workspaceServiceMode === "remote") {
    return createRemoteWorkspaceService({
      baseUrl: env.VITE_API_BASE_URL || "",
    });
  }

  return createInMemoryDummyWorkspaceService<FileTreeNode, Ree["source_type"]>({
    getWorkspaceFiles: () => virtualFiles,
    updateWorkspaceFiles: (virtualFilesUpdate) =>
      dispatch(explorerActions.setVirtualFiles(virtualFilesUpdate)),
    upsertFile: (previous, path, content) => upsertWorkspaceFile(previous, path, content),
    deleteFile: (previous, path) => removeWorkspaceFile(previous, path),
    runScript: async (scriptKey: string): Promise<WorkspaceServiceLogEntry> => {
      const params =
        (serviceParams as Partial<Record<string, GenericServiceParams>>)[scriptKey] ?? {};
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
          origin_url: "",
          _sourceIncluded: true,
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
  onRunStarted?: (key: string, runId: string) => void;
  onRunFinished?: (key: string) => void;
}

export function createSourceActions({
  ree,
  workspaceService,
  dispatch,
  onSourceChange,
  showToast,
  onRunStarted,
  onRunFinished,
}: CreateSourceActionsArgs) {
  const cloneTree = (nodes: FileTreeNode[]): FileTreeNode[] =>
    nodes.map((node) => ({
      ...node,
      children: node.children ? cloneTree(node.children) : undefined,
    }));

  const refreshWorkspaceFiles = async () => {
    const workspace = await workspaceService.getWorkspace(WORKSPACE_ID);
    dispatch(explorerActions.setVirtualFiles(workspace.files));
    return workspace.files;
  };

  const handleDownloadSourceFiles = async (originType: Ree["source_type"], sourceUrl: string) => {
    if (ree._sourceAvailable && ree._sourceAcquiredBy === "upload") {
      showToast(
        "Source already provided via tarball upload. Change source to switch method.",
        "error",
      );
      return;
    }
    const normalizedSourceUrl = sourceUrl.trim();
    if (!normalizedSourceUrl || !originType) {
      showToast("Set origin URL and origin type first", "error");
      return;
    }
    onSourceChange({ silent: true });
    dispatch(
      explorerActions.setActionStates((prevStates) => ({ ...prevStates, source: "loading" })),
    );
    if (!workspaceService.startWorkflowRun || !workspaceService.getWorkflowRun) {
      await workspaceService.resetWorkspace(
        WORKSPACE_ID,
        serializeWorkspaceResetPayload({
          mode: "download",
          source: normalizedSourceUrl,
          sourceType: originType,
        }),
      );
    } else {
      const run = await workspaceService.startWorkflowRun(WORKSPACE_ID, "source", {
        mode: "download",
        source: normalizedSourceUrl,
        sourceType: originType,
      });
      onRunStarted?.("source", run.runId);
      const result = await pollWorkflowRun(workspaceService, {
        workspaceId: WORKSPACE_ID,
        runId: run.runId,
        onUpdate: (update) => {
          dispatch(
            explorerActions.setServiceLogs((prevLogs) => ({
              ...prevLogs,
              source: { lines: update.lines, ts: update.ts },
            })),
          );
        },
      });
      onRunFinished?.("source");
      if (result.status === "failed" || result.status === "canceled") {
        dispatch(
          explorerActions.setActionStates((prevStates) => ({ ...prevStates, source: "done" })),
        );
        showToast(`Source ${result.status}`, "error");
        return;
      }
    }

    dispatch(explorerActions.setActionStates((prevStates) => ({ ...prevStates, source: "done" })));
    dispatch(explorerActions.setBadges((prevBadges) => ({ ...prevBadges, source: true })));
    const initialTs = new Date().toISOString();
    dispatch(
      explorerActions.setTimestamps((prevTimestamps) => ({ ...prevTimestamps, source: initialTs })),
    );
    const workspaceFiles = await refreshWorkspaceFiles();
    const snapshotFiles = cloneTree(workspaceFiles);
    const ts = new Date().toISOString();
    const repoBase =
      (normalizedSourceUrl.split("/").filter(Boolean).pop() || "source").replace(
        /\.(git|tar\.gz|tgz|zip)$/i,
        "",
      ) || "source";
    const snapshotArchiveName = normalizeSnapshotArchiveName(`${repoBase}-original.tar.gz`);
    dispatch(explorerActions.setImmutableSourceSnapshotFiles(snapshotFiles));
    dispatch(explorerActions.setImmutableSourceSnapshotArchiveName(snapshotArchiveName));
    dispatch(
      explorerActions.setRee((prevRee) => ({
        ...prevRee,
        origin_url: normalizedSourceUrl,
        source_type: originType,
        _sourceAvailable: workspaceFiles.length > 0,
        _sourceAcquiredBy: "download",
        _uploadedArchive: "",
        _sourceSnapshotArchive: snapshotArchiveName,
        _sourceSnapshotCapturedAt: ts,
      })),
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
    const archiveName = payload.archiveName || "source.tar.gz";
    const runUpload = async () => {
      try {
        dispatch(
          explorerActions.setActionStates((prevStates) => ({ ...prevStates, source: "loading" })),
        );
        let archiveContentBase64: string | undefined;
        if (payload.archiveFile) {
          const rawBuffer = await payload.archiveFile.arrayBuffer();
          const bytes = new Uint8Array(rawBuffer);
          let binary = "";
          for (let i = 0; i < bytes.length; i += 1) {
            binary += String.fromCharCode(bytes[i]);
          }
          archiveContentBase64 = btoa(binary);
        }

        if (!workspaceService.startWorkflowRun || !workspaceService.getWorkflowRun) {
          await workspaceService.resetWorkspace(
            WORKSPACE_ID,
            serializeWorkspaceResetPayload({ mode: "upload", archiveName, archiveContentBase64 }),
          );
        } else {
          const run = await workspaceService.startWorkflowRun(WORKSPACE_ID, "source", {
            mode: "upload",
            archiveName,
            archiveContentBase64,
          });
          onRunStarted?.("source", run.runId);
          const result = await pollWorkflowRun(workspaceService, {
            workspaceId: WORKSPACE_ID,
            runId: run.runId,
            onUpdate: (update) => {
              dispatch(
                explorerActions.setServiceLogs((prevLogs) => ({
                  ...prevLogs,
                  source: { lines: update.lines, ts: update.ts },
                })),
              );
            },
          });
          onRunFinished?.("source");
          if (result.status === "failed" || result.status === "canceled") {
            dispatch(
              explorerActions.setActionStates((prevStates) => ({ ...prevStates, source: "done" })),
            );
            showToast(`Source ${result.status}`, "error");
            return;
          }
        }
        const workspaceFiles = await refreshWorkspaceFiles();
        const snapshotFiles = cloneTree(workspaceFiles);
        const snapshotArchiveName = normalizeSnapshotArchiveName(archiveName);
        const ts = new Date().toISOString();
        dispatch(explorerActions.setImmutableSourceSnapshotFiles(snapshotFiles));
        dispatch(explorerActions.setImmutableSourceSnapshotArchiveName(snapshotArchiveName));
        dispatch(
          explorerActions.setRee((prevRee) => ({
            ...prevRee,
            origin_url: "",
            _sourceIncluded: true,
            _uploadedArchive: archiveName,
            source_type: "",
            _sourceAvailable: workspaceFiles.length > 0,
            _sourceAcquiredBy: "upload",
            _sourceSnapshotArchive: snapshotArchiveName,
            _sourceSnapshotCapturedAt: ts,
          })),
        );
        dispatch(explorerActions.setBadges((prevBadges) => ({ ...prevBadges, source: true })));
        dispatch(
          explorerActions.setTimestamps((prevTimestamps) => ({ ...prevTimestamps, source: ts })),
        );
        dispatch(
          explorerActions.setActionStates((prevStates) => ({ ...prevStates, source: "done" })),
        );
        showToast("Archive extracted into workspace", "success");
      } catch (error) {
        dispatch(
          explorerActions.setActionStates((prevStates) => ({ ...prevStates, source: "done" })),
        );
        showToast(
          error instanceof Error
            ? `Failed to extract archive: ${error.message}`
            : "Failed to extract archive",
          "error",
        );
      }
    };
    void runUpload();
  };

  const handleRemoveWorkspaceSource = () => {
    onSourceChange({ silent: true });
    const runClear = async () => {
      try {
        await workspaceService.resetWorkspace(
          WORKSPACE_ID,
          serializeWorkspaceResetPayload({ mode: "clear" }),
        );
        await refreshWorkspaceFiles();
        dispatch(explorerActions.setImmutableSourceSnapshotFiles([]));
        dispatch(explorerActions.setImmutableSourceSnapshotArchiveName(""));
        dispatch(
          explorerActions.setRee((prevRee) => ({
            ...prevRee,
            origin_url: "",
            _sourceAvailable: false,
            _sourceAcquiredBy: undefined,
            _uploadedArchive: "",
            _sourceSnapshotArchive: "",
            _sourceSnapshotCapturedAt: "",
          })),
        );
      } catch (error) {
        showToast(
          error instanceof Error
            ? `Failed to clear source: ${error.message}`
            : "Failed to clear source",
          "error",
        );
      }
    };
    void runClear();
    showToast("Source files removed from workspace — choose download or upload again", "info");
  };

  return {
    handleDownloadSourceFiles,
    handleWorkspaceUpload,
    handleRemoveWorkspaceSource,
  };
}
