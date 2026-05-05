import type { QueryClient } from "@tanstack/react-query";
import type { AppShellClock } from "../../../app/bootstrap/ports";
import type { ReeClient } from "../../../data/ree/client";
import type { WorkflowRunsClient } from "../../../data/workflow-runs/client";
import type { ReeViewState } from "../../../domain/ree/ReeViewState";
import type { FileTreeNode } from "../../../domain/workspace/FileTree";
import type { WorkspaceWorkflowDispatch } from "../workflow-runs/commandExecutors";
import type { ShowToast } from "../workflow-runs/types";
import { createSourceActions, resetWorkflowOnSourceChange } from "./sourceLifecycle";

interface CreateSourceAdapterArgs {
  ree: ReeViewState;
  reeClient: ReeClient<FileTreeNode>;
  workflowRunsClient: WorkflowRunsClient;
  reeId: string;
  queryClient: QueryClient;
  dispatch: WorkspaceWorkflowDispatch;
  refreshWorkspaceFiles: () => Promise<FileTreeNode[]>;
  showToast: ShowToast;
  clock: AppShellClock;
  sleep: (ms: number) => Promise<void>;
  onRunStarted?: (key: string, runId: string) => void;
  onRunFinished?: (key: string) => void;
}

export function createSourceAdapter({
  ree,
  reeClient,
  workflowRunsClient,
  reeId,
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
    reeClient,
    workflowRunsClient,
    reeId,
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
