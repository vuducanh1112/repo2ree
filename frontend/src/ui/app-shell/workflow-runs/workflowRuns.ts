import type { QueryClient } from "@tanstack/react-query";
import type { AppShellRuntimePorts } from "../../../application/app-shell/AppShellPorts";
import type {
  WorkflowRunLogEntry,
  WorkflowRunRecord,
} from "../../../application/ports/repositoryTypes";
import type { WorkflowRunRepository } from "../../../application/ports/WorkflowRunRepository";
import { executeWorkflowStep } from "../../../application/workflow/executeWorkflowStep";
import type { GenericWorkflowParams } from "../../../application/workflow/WorkflowStepTypes";
import type {
  WorkflowStepCommand,
  WorkflowStepHandlerMap,
} from "../../../application/workflow/workflowStepCommands";
import type { ReeFile } from "../../../domain/ree/ReeTypes";
import type { ReeViewState } from "../../../domain/ree/ReeViewState";
import type { FileTreeNode } from "../../../domain/workspace/FileTree";
import { executeWorkflowStepCommands, type WorkspaceWorkflowDispatch } from "./commandExecutors";
import { pollWorkflowRun } from "./pollWorkflowRun";
import type { ShowToast } from "./types";

interface ExecuteServiceRunArgs {
  key: string;
  params: GenericWorkflowParams;
  ree: ReeViewState;
  level: number;
  workspaceFiles: FileTreeNode[];
  dispatch: WorkspaceWorkflowDispatch;
  persistWorkspaceFile: (path: string, content: string) => void;
  showToast: ShowToast;
  workflowStepHandlers: WorkflowStepHandlerMap;
  workflowRunRepository: WorkflowRunRepository;
  workspaceId: string;
  queryClient: QueryClient;
  startWorkflowRun: (
    scriptKey: string,
    params?: Record<string, string | boolean | number | null | undefined>,
  ) => Promise<WorkflowRunRecord>;
  ports: AppShellRuntimePorts;
  refreshWorkspace: () => Promise<{
    workspaceFiles: FileTreeNode[];
    reeArtifactFiles: ReeFile[];
    ree?: ReeViewState;
  }>;
  onRunStarted?: (key: string, runId: string) => void;
  onRunFinished?: (key: string) => void;
}

export async function executeWorkflowRunAction({
  key,
  params,
  ree,
  level,
  workspaceFiles,
  dispatch,
  persistWorkspaceFile,
  showToast,
  workflowStepHandlers,
  workflowRunRepository,
  workspaceId,
  queryClient,
  startWorkflowRun,
  ports,
  refreshWorkspace,
  onRunStarted,
  onRunFinished,
}: ExecuteServiceRunArgs): Promise<WorkflowRunLogEntry> {
  const runCommands = (commands: WorkflowStepCommand[]) =>
    executeWorkflowStepCommands(commands, { dispatch, persistWorkspaceFile, showToast });
  return executeWorkflowStep({
    key,
    params,
    ree,
    level,
    workspaceFiles,
    workflowRunner: {
      startWorkflowRun: (scriptKey, runParams) => startWorkflowRun(scriptKey, runParams),
      pollRun: (runId, onUpdateLogs) =>
        pollWorkflowRun(queryClient, workflowRunRepository, {
          workspaceId,
          runId,
          onUpdate: onUpdateLogs,
          clock: ports.clock,
          sleep: ports.sleep,
        }),
    },
    workflowStepHandlers,
    generatedIds: {
      swhid: `swh:1:dir:${ports.random.hex(12)}`,
      zenodoDoi: `10.5281/zenodo.${ports.random.int(1000000, 9999999)}`,
      dataverseDoi: `doi:10.5072/DVN/${ports.random.int(100000, 999999)}`,
    },
    executeCommands: runCommands,
    refreshWorkspace: async () => {
      const workspace = await refreshWorkspace();
      return {
        files: workspace.workspaceFiles,
        reeFiles: workspace.reeArtifactFiles,
        ree: workspace.ree,
      };
    },
    onRunStarted,
    onRunFinished,
  });
}
