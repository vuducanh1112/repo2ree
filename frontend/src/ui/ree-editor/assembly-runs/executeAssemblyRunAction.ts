import type { QueryClient } from "@tanstack/react-query";
import type { AppShellRuntimePorts } from "../../../app/bootstrap/ports";
import type {
  AssemblyCommand,
  AssemblyCommandPlannerMap,
} from "../../../application/ree-assembly/assemblyCommands";
import type { GenericReeAssemblyParams } from "../../../application/ree-assembly/assemblyStepTypes";
import { executeAssemblyRun } from "../../../application/ree-assembly/executeAssemblyRun";
import type { ReeEditorViewModel } from "../../../application/ree-editor/reeEditorViewModel";
import type { ExecutionRunsClient } from "../../../data/execution-runs/client";
import type { ExecutionRun } from "../../../domain/execution/ExecutionRun";
import type { RawReeDraftSlices } from "../../../domain/ree/mapRawReeDraft";
import type { LogEntry, ReeFile } from "../../../domain/ree/ReeTypes";
import type { FileTreeNode } from "../../../domain/workspace/FileTree";
import type { ShowToast } from "../types";
import { executeAssemblyCommands, type ReeEditorDispatch } from "./assemblyActionEffects";
import { pollExecutionRun } from "./pollExecutionRun";

interface ExecuteAssemblyRunActionArgs {
  key: string;
  params: GenericReeAssemblyParams;
  ree: ReeEditorViewModel;
  level: number;
  workspaceFiles: FileTreeNode[];
  dispatch: ReeEditorDispatch;
  persistWorkspaceFile: (path: string, content: string) => void;
  showToast: ShowToast;
  assemblyCommandPlanners: AssemblyCommandPlannerMap;
  executionRunsClient: ExecutionRunsClient;
  reeId: string;
  queryClient: QueryClient;
  startExecutionRun: (
    scriptKey: string,
    params?: Record<string, string | boolean | number | null | undefined>,
  ) => Promise<ExecutionRun>;
  ports: AppShellRuntimePorts;
  refreshWorkspace: () => Promise<{
    workspaceFiles: FileTreeNode[];
    reeArtifactFiles: ReeFile[];
    ree?: RawReeDraftSlices;
  }>;
  onRunStarted?: (key: string, runId: string) => void;
  onRunFinished?: (key: string) => void;
}

export async function executeAssemblyRunAction({
  key,
  params,
  ree,
  level,
  workspaceFiles,
  dispatch,
  persistWorkspaceFile,
  showToast,
  assemblyCommandPlanners,
  executionRunsClient,
  reeId,
  queryClient,
  startExecutionRun,
  ports,
  refreshWorkspace,
  onRunStarted,
  onRunFinished,
}: ExecuteAssemblyRunActionArgs): Promise<LogEntry> {
  const runCommands = (commands: AssemblyCommand[]) =>
    executeAssemblyCommands(commands, { dispatch, persistWorkspaceFile, showToast });

  return executeAssemblyRun({
    key,
    params,
    ree,
    level,
    workspaceFiles,
    executionRunner: {
      startExecutionRun: (scriptKey, runParams) => startExecutionRun(scriptKey, runParams),
      pollRun: (runId, onUpdateLogs) =>
        pollExecutionRun(queryClient, executionRunsClient, {
          reeId,
          runId,
          onUpdate: onUpdateLogs,
          clock: ports.clock,
          sleep: ports.sleep,
        }),
    },
    assemblyCommandPlanners,
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
