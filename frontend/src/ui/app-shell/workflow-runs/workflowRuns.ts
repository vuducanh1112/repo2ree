import type { QueryClient } from "@tanstack/react-query";
import type { AppShellRuntimePorts } from "../../../app/bootstrap/ports";
import type {
  AssemblyCommand,
  AssemblyCommandPlannerMap,
} from "../../../application/ree-assembly/assemblyCommands";
import type { GenericReeAssemblyParams } from "../../../application/ree-assembly/assemblyStepTypes";
import { executeAssemblyRun } from "../../../application/ree-assembly/executeAssemblyRun";
import type { ExecutionRunsClient } from "../../../data/execution-runs/client";
import type { ExecutionRun } from "../../../domain/execution/ExecutionRun";
import type { LogEntry, ReeFile } from "../../../domain/ree/ReeTypes";
import type { ReeViewState } from "../../../domain/ree/ReeViewState";
import type { FileTreeNode } from "../../../domain/workspace/FileTree";
import { executeWorkflowStepCommands, type WorkspaceWorkflowDispatch } from "./commandExecutors";
import { pollWorkflowRun } from "./pollWorkflowRun";
import type { ShowToast } from "./types";

interface ExecuteServiceRunArgs {
  key: string;
  params: GenericReeAssemblyParams;
  ree: ReeViewState;
  level: number;
  workspaceFiles: FileTreeNode[];
  dispatch: WorkspaceWorkflowDispatch;
  persistWorkspaceFile: (path: string, content: string) => void;
  showToast: ShowToast;
  workflowStepHandlers: AssemblyCommandPlannerMap;
  workflowRunsClient: ExecutionRunsClient;
  reeId: string;
  queryClient: QueryClient;
  startWorkflowRun: (
    scriptKey: string,
    params?: Record<string, string | boolean | number | null | undefined>,
  ) => Promise<ExecutionRun>;
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
  workflowRunsClient,
  reeId,
  queryClient,
  startWorkflowRun,
  ports,
  refreshWorkspace,
  onRunStarted,
  onRunFinished,
}: ExecuteServiceRunArgs): Promise<LogEntry> {
  const runCommands = (commands: AssemblyCommand[]) =>
    executeWorkflowStepCommands(commands, { dispatch, persistWorkspaceFile, showToast });
  return executeAssemblyRun({
    key,
    params,
    ree,
    level,
    workspaceFiles,
    executionRunner: {
      startExecutionRun: (scriptKey, runParams) => startWorkflowRun(scriptKey, runParams),
      pollRun: (runId, onUpdateLogs) =>
        pollWorkflowRun(queryClient, workflowRunsClient, {
          reeId,
          runId,
          onUpdate: onUpdateLogs,
          clock: ports.clock,
          sleep: ports.sleep,
        }),
    },
    assemblyCommandPlanners: workflowStepHandlers,
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
