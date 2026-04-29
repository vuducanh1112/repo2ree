import { computeEvaluateLevelFromFiles } from "../../../../application/explorer/dependencyParser";
import type { ExplorerRuntimePorts } from "../../../../application/explorer/runtimePorts";
import type {
  ServiceRunCommand,
  ServiceRunHandlerMap,
} from "../../../../application/explorer/serviceRunCommands";
import { deriveServiceRunLevel } from "../../../../application/explorer/serviceRunPlanning";
import { executeServiceRunUseCase } from "../../../../application/explorer/serviceRunUseCase";
import type {
  IWorkspaceService,
  WorkspaceServiceLogEntry,
} from "../../../../services/workspaceService";
import type { FileTreeNode, Ree } from "../../../../types";
import type { GenericServiceParams } from "../../../../types/services";
import { makeLogs } from "../../services/logGenerator";
import { type ExplorerWorkflowDispatch, executeServiceRunCommands } from "./commandExecutors";
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
  serviceRunHandlers: ServiceRunHandlerMap;
  workspaceService: IWorkspaceService<FileTreeNode>;
  workspaceId: string;
  ports: ExplorerRuntimePorts;
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
  serviceRunHandlers,
  workspaceService,
  workspaceId,
  ports,
  onRunStarted,
  onRunFinished,
}: ExecuteServiceRunArgs): Promise<WorkspaceServiceLogEntry> {
  const runCommands = (commands: ServiceRunCommand[]) =>
    executeServiceRunCommands(commands, { dispatch, persistWorkspaceFile, showToast });
  const startWorkflowRun =
    workspaceService.startWorkflowRun && workspaceService.getWorkflowRun
      ? workspaceService.startWorkflowRun.bind(workspaceService)
      : undefined;

  return executeServiceRunUseCase({
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
        const newLevel = deriveServiceRunLevel(key, level, evaluatedLevel);
        const lines = makeLogs(key, ree, params, newLevel);
        return {
          status: "succeeded",
          lines,
          ts: ports.clock.nowIso(),
        };
      },
    },
    serviceRunHandlers,
    generatedIds: {
      swhid: `swh:1:dir:${ports.random.hex(12)}`,
      zenodoDoi: `10.5281/zenodo.${ports.random.int(1000000, 9999999)}`,
      dataverseDoi: `doi:10.5072/DVN/${ports.random.int(100000, 999999)}`,
    },
    executeCommands: runCommands,
    refreshWorkspace: () => workspaceService.getWorkspace(workspaceId),
    onRunStarted,
    onRunFinished,
  });
}
