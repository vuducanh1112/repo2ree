import type {
  WorkflowRunLogEntry,
  WorkspaceGateway,
} from "../../../application/ports/WorkspaceGateway";
import { executeWorkflowStep } from "../../../application/workflow/executeWorkflowStep";
import type { GenericServiceParams } from "../../../application/workflow/WorkflowStepTypes";
import type {
  WorkflowStepCommand,
  WorkflowStepHandlerMap,
} from "../../../application/workflow/workflowStepCommands";
import type { WorkspaceEditorRuntimePorts } from "../../../application/workspace-editor/WorkspaceEditorPorts";
import type { Ree } from "../../../domain/ree/ReeSpec";
import type { ReeFile } from "../../../domain/ree/ReeTypes";
import type { FileTreeNode } from "../../../domain/workspace/FileTree";
import { executeWorkflowStepCommands, type WorkspaceWorkflowDispatch } from "./commandExecutors";
import { pollWorkflowRun } from "./pollWorkflowRun";
import type { ShowToast } from "./types";

interface ExecuteServiceRunArgs {
  key: string;
  params: GenericServiceParams;
  ree: Ree;
  level: number;
  virtualFiles: FileTreeNode[];
  dispatch: WorkspaceWorkflowDispatch;
  persistWorkspaceFile: (path: string, content: string) => void;
  showToast: ShowToast;
  workflowStepHandlers: WorkflowStepHandlerMap;
  workspaceService: WorkspaceGateway<FileTreeNode>;
  workspaceId: string;
  ports: WorkspaceEditorRuntimePorts;
  refreshWorkspace: () => Promise<{
    virtualFiles: FileTreeNode[];
    workspaceReeFiles: ReeFile[];
    ree?: Ree;
  }>;
  onRunStarted?: (key: string, runId: string) => void;
  onRunFinished?: (key: string) => void;
}

export async function executeServiceRunAction({
  key,
  params,
  ree,
  level,
  virtualFiles,
  dispatch,
  persistWorkspaceFile,
  showToast,
  workflowStepHandlers,
  workspaceService,
  workspaceId,
  ports,
  refreshWorkspace,
  onRunStarted,
  onRunFinished,
}: ExecuteServiceRunArgs): Promise<WorkflowRunLogEntry> {
  const runCommands = (commands: WorkflowStepCommand[]) =>
    executeWorkflowStepCommands(commands, { dispatch, persistWorkspaceFile, showToast });
  if (!workspaceService.startWorkflowRun || !workspaceService.getWorkflowRun) {
    throw new Error("Workspace gateway does not support workflow runs");
  }
  const startWorkflowRun = workspaceService.startWorkflowRun.bind(workspaceService);

  return executeWorkflowStep({
    key,
    params,
    ree,
    level,
    virtualFiles,
    workflowRunner: {
      startWorkflowRun: (scriptKey, runParams) =>
        startWorkflowRun(workspaceId, scriptKey, runParams),
      pollRun: (runId, onUpdateLogs) =>
        pollWorkflowRun(workspaceService, {
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
        files: workspace.virtualFiles,
        reeFiles: workspace.workspaceReeFiles,
        ree: workspace.ree,
      };
    },
    onRunStarted,
    onRunFinished,
  });
}
