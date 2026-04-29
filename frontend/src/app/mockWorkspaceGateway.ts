import type { WorkspaceEditorRuntimePorts } from "../application/workspace/workspaceEditorPorts";
import { PAGE } from "../constants/pages";
import type { WorkspaceEditorAction } from "../context";
import { workspaceEditorActions } from "../context";
import {
  removeWorkspaceFileByPath,
  upsertWorkspaceFileByPath,
} from "../domain/workspace/fileTreeOps";
import type { FileTreeNode, Ree, ServiceParams } from "../types";
import type { GenericServiceParams } from "../types/workflowSteps";
import { normalizeSnapshotArchiveName } from "../utils";
import {
  cloneDummyWorkspaceTree,
  createInMemoryWorkspaceGateway,
  MOCK_FILES,
  makeDummyWorkspaceFromArchiveUpload,
  makeDummyWorkspaceFromOrigin,
} from "../workspace/InMemoryWorkspaceGateway";
import type { WorkflowRunLogEntry, WorkspaceGateway } from "../workspace/WorkspaceGateway";

interface CreateMockWorkspaceServiceArgs {
  ree: Ree;
  virtualFiles: FileTreeNode[];
  serviceParams: ServiceParams;
  dispatch: (action: WorkspaceEditorAction) => void;
  ports: WorkspaceEditorRuntimePorts;
  executeServiceRun: (key: string, params?: GenericServiceParams) => Promise<WorkflowRunLogEntry>;
}

function upsertWorkspaceFile(nodes: FileTreeNode[], path: string, content: string): FileTreeNode[] {
  return upsertWorkspaceFileByPath(nodes, path, content, { tag: PAGE.SOURCE });
}

function removeWorkspaceFile(nodes: FileTreeNode[], path: string): FileTreeNode[] {
  return removeWorkspaceFileByPath(nodes, path);
}

export function createMockWorkspaceGateway({
  ree,
  virtualFiles,
  serviceParams,
  dispatch,
  ports,
  executeServiceRun,
}: CreateMockWorkspaceServiceArgs): WorkspaceGateway<FileTreeNode> {
  return createInMemoryWorkspaceGateway<FileTreeNode, Ree["source_type"]>({
    getWorkspaceFiles: () => virtualFiles,
    updateWorkspaceFiles: (virtualFilesUpdate) =>
      dispatch(workspaceEditorActions.setVirtualFiles(virtualFilesUpdate)),
    upsertFile: (previous, path, content) => upsertWorkspaceFile(previous, path, content),
    deleteFile: (previous, path) => removeWorkspaceFile(previous, path),
    runScript: async (scriptKey: string): Promise<WorkflowRunLogEntry> => {
      const params =
        (serviceParams as Partial<Record<string, GenericServiceParams>>)[scriptKey] ?? {};
      return executeServiceRun(scriptKey, params);
    },
    clearWorkspace: () => {
      dispatch(workspaceEditorActions.setVirtualFiles([]));
      dispatch(workspaceEditorActions.setWorkspaceReeFiles([]));
      dispatch(workspaceEditorActions.setImmutableSourceSnapshotFiles([]));
      dispatch(workspaceEditorActions.setImmutableSourceSnapshotArchiveName(""));
      dispatch(
        workspaceEditorActions.setRee((prevRee) => ({
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
      const ts = ports.clock.nowIso();
      const workspaceFiles = makeDummyWorkspaceFromArchiveUpload(
        MOCK_FILES,
        archiveName,
        PAGE.SOURCE,
      );
      const snapshotFiles = cloneDummyWorkspaceTree(workspaceFiles);
      const snapshotArchiveName = normalizeSnapshotArchiveName(archiveName);

      dispatch(workspaceEditorActions.setVirtualFiles(workspaceFiles));
      dispatch(workspaceEditorActions.setWorkspaceReeFiles([]));
      dispatch(workspaceEditorActions.setImmutableSourceSnapshotFiles(snapshotFiles));
      dispatch(workspaceEditorActions.setImmutableSourceSnapshotArchiveName(snapshotArchiveName));
      dispatch(
        workspaceEditorActions.setRee((prevRee) => ({
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

      const ts = ports.clock.nowIso();
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

      dispatch(workspaceEditorActions.setVirtualFiles(workspaceFiles));
      dispatch(workspaceEditorActions.setWorkspaceReeFiles([]));
      dispatch(workspaceEditorActions.setImmutableSourceSnapshotFiles(snapshotFiles));
      dispatch(workspaceEditorActions.setImmutableSourceSnapshotArchiveName(snapshotArchiveName));
      dispatch(
        workspaceEditorActions.setRee((prevRee) => ({
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
