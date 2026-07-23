import type { RawReeIntentSlices } from "@core/ree/mapRawReeIntent";
import type { LogEntry, ReeFile } from "@core/ree/ReeTypes";
import type { ReeEditorViewModel } from "@core/ree-editor/reeEditorViewModel";
import { executeStepRun } from "@core/ree-steps/executeStepRun";
import type { StepCommand, StepCommandPlannerMap } from "@core/ree-steps/stepCommands";
import type { GenericReeStepParams } from "@core/ree-steps/stepTypes";
import type { ReeRun } from "@core/runs/ReeRun";
import type { FileTreeNode } from "@core/workspace/FileTree";
import type { AppShellRuntimePorts } from "@shell/app/bootstrap/ports";
import type { ReeRunsClient } from "@shell/data/runs/client";
import { observeReeRun } from "@shell/data/runs/queries";
import type { QueryClient } from "@tanstack/react-query";
import type { ShowToast } from "../types";
import { executeStepCommands, type ReeEditorDispatch } from "./stepActionEffects";

interface ExecuteStepRunActionArgs {
  key: string;
  params: GenericReeStepParams;
  ree: ReeEditorViewModel;
  workspaceFiles: FileTreeNode[];
  dispatch: ReeEditorDispatch;
  persistWorkspaceFile: (path: string, content: string) => void;
  showToast: ShowToast;
  stepCommandPlanners: StepCommandPlannerMap;
  executionRunsClient: ReeRunsClient;
  reeId: string;
  queryClient: QueryClient;
  startReeRun: (
    scriptKey: string,
    params?: Record<string, string | boolean | number | null | undefined>,
  ) => Promise<ReeRun>;
  ports: AppShellRuntimePorts;
  refreshWorkspace: () => Promise<{
    workspaceFiles: FileTreeNode[];
    reeArtifactFiles: ReeFile[];
    ree?: RawReeIntentSlices;
  }>;
  onRunStarted?: (key: string, runId: string) => void;
  onRunFinished?: (key: string, runId: string) => void;
}

export async function executeStepRunAction({
  key,
  params,
  ree,
  workspaceFiles,
  dispatch,
  persistWorkspaceFile,
  showToast,
  stepCommandPlanners,
  executionRunsClient,
  reeId,
  queryClient,
  startReeRun,
  ports,
  refreshWorkspace,
  onRunStarted,
  onRunFinished,
}: ExecuteStepRunActionArgs): Promise<LogEntry> {
  const runCommands = (commands: StepCommand[]) =>
    executeStepCommands(commands, { dispatch, persistWorkspaceFile, showToast });

  return executeStepRun({
    key,
    params,
    ree,
    workspaceFiles,
    executionRunner: {
      startReeRun: (scriptKey, runParams) => startReeRun(scriptKey, runParams),
      pollRun: (runId, onUpdateLogs) =>
        observeReeRun(queryClient, executionRunsClient, {
          reeId,
          runId,
          onUpdate: onUpdateLogs,
          sleep: ports.sleep,
        }),
    },
    stepCommandPlanners,
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
