import { executeWorkflowStep } from "../../../../application/workflow/executeWorkflowStep";
import { computeEvaluateLevelFromFiles } from "../../../../application/workflow/workflowDependencyAnalysis";
import { deriveWorkflowStepLevel } from "../../../../application/workflow/workflowRunPolicy";
import type {
  WorkflowStepCommand,
  WorkflowStepHandlerMap,
} from "../../../../application/workflow/workflowStepCommands";
import type { WorkspaceEditorRuntimePorts } from "../../../../application/workspace/workspaceEditorPorts";
import type { FileTreeNode, Ree, ReeFile } from "../../../../types";
import type { GenericServiceParams } from "../../../../types/workflowSteps";
import type { WorkflowRunLogEntry, WorkspaceGateway } from "../../../../workspace/WorkspaceGateway";
import { makeLogs } from "../../services/logGenerator";
import { type ExplorerWorkflowDispatch, executeWorkflowStepCommands } from "./commandExecutors";
import { pollWorkflowRun } from "./pollWorkflowRun";
import type { ShowToast } from "./types";

interface ExecuteServiceRunArgs {
  key: string;
  params: GenericServiceParams;
  ree: Ree;
  level: number;
  virtualFiles: FileTreeNode[];
  dispatch: ExplorerWorkflowDispatch;
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
  const startWorkflowRun =
    workspaceService.startWorkflowRun && workspaceService.getWorkflowRun
      ? workspaceService.startWorkflowRun.bind(workspaceService)
      : undefined;

  return executeWorkflowStep({
    key,
    params,
    ree,
    level,
    virtualFiles,
    workflowRunner: {
      startWorkflowRun: startWorkflowRun
        ? (scriptKey, runParams) => startWorkflowRun(workspaceId, scriptKey, runParams)
        : undefined,
      pollRun: (runId, onUpdateLogs) =>
        pollWorkflowRun(workspaceService, {
          workspaceId,
          runId,
          onUpdate: onUpdateLogs,
          clock: ports.clock,
          sleep: ports.sleep,
        }),
      createMockResult: async () => {
        await ports.sleep(1600 + ports.random.int(0, 700));
        const evaluatedLevel = computeEvaluateLevelFromFiles(virtualFiles || []);
        const newLevel = deriveWorkflowStepLevel(key, level, evaluatedLevel);
        const lines = makeLogs(key, ree, params, newLevel);
        return {
          status: "succeeded",
          lines,
          ts: ports.clock.nowIso(),
        };
      },
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
