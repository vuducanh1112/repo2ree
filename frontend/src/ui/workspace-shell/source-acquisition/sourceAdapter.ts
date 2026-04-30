import type { QueryClient } from "@tanstack/react-query";
import type { WorkflowRunRepository } from "../../../application/ports/WorkflowRunRepository";
import type { WorkspaceRepository } from "../../../application/ports/WorkspaceRepository";
import type { WorkspaceShellClock } from "../../../application/workspace-shell/WorkspaceShellPorts";
import type { Ree } from "../../../domain/ree/ReeSpec";
import type { FileTreeNode } from "../../../domain/workspace/FileTree";
import type { WorkspaceWorkflowDispatch } from "../workflow-runs/commandExecutors";
import type { ShowToast } from "../workflow-runs/types";
import { createSourceActions, resetWorkflowOnSourceChange } from "./sourceLifecycle";

interface CreateSourceAdapterArgs {
  ree: Ree;
  workspaceRepository: WorkspaceRepository<FileTreeNode>;
  workflowRunRepository: WorkflowRunRepository;
  workspaceId: string;
  queryClient: QueryClient;
  dispatch: WorkspaceWorkflowDispatch;
  refreshWorkspaceFiles: () => Promise<FileTreeNode[]>;
  showToast: ShowToast;
  clock: WorkspaceShellClock;
  sleep: (ms: number) => Promise<void>;
  onRunStarted?: (key: string, runId: string) => void;
  onRunFinished?: (key: string) => void;
}

export function createSourceAdapter({
  ree,
  workspaceRepository,
  workflowRunRepository,
  workspaceId,
  queryClient,
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
    workspaceRepository,
    workflowRunRepository,
    workspaceId,
    queryClient,
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
