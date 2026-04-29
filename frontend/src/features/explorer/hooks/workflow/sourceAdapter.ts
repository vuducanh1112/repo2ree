import type { ExplorerClock } from "../../../../application/explorer/runtimePorts";
import type { IWorkspaceService } from "../../../../services/workspaceService";
import type { FileTreeNode, Ree } from "../../../../types";
import type { ExplorerWorkflowDispatch } from "./commandExecutors";
import { createSourceActions, resetWorkflowOnSourceChange } from "./sourceLifecycle";
import type { ShowToast } from "./types";

interface CreateSourceAdapterArgs {
  ree: Ree;
  workspaceService: IWorkspaceService<FileTreeNode>;
  workspaceId: string;
  dispatch: ExplorerWorkflowDispatch;
  refreshWorkspaceFiles: () => Promise<FileTreeNode[]>;
  showToast: ShowToast;
  clock: ExplorerClock;
  sleep: (ms: number) => Promise<void>;
  onRunStarted?: (key: string, runId: string) => void;
  onRunFinished?: (key: string) => void;
}

export function createSourceAdapter({
  ree,
  workspaceService,
  workspaceId,
  dispatch,
  refreshWorkspaceFiles,
  showToast,
  clock,
  sleep,
  onRunStarted,
  onRunFinished,
}: CreateSourceAdapterArgs) {
  const resetSourceWorkflow = (options: { silent?: boolean } = {}) => {
    resetWorkflowOnSourceChange(dispatch, showToast, options);
  };

  const sourceActions = createSourceActions({
    ree,
    workspaceService,
    workspaceId,
    dispatch,
    refreshWorkspaceFiles,
    onSourceChange: resetSourceWorkflow,
    showToast,
    clock,
    sleep,
    onRunStarted,
    onRunFinished,
  });

  return {
    ...sourceActions,
    resetSourceWorkflow,
  };
}
