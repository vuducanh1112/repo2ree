import type { ServiceRunCommand } from "../../../../application/explorer/serviceRunCommands";
import type { SourceCommand } from "../../../../application/explorer/sourceCommands";
import type { AppAction } from "../../../../context";
import { explorerActions } from "../../../../context";
import type { ShowToast } from "./types";

export type ExplorerWorkflowDispatch = (action: AppAction) => void;

interface ServiceRunCommandEffects {
  dispatch: ExplorerWorkflowDispatch;
  persistWorkspaceFile: (path: string, content: string) => void;
  showToast: ShowToast;
}

export function executeServiceRunCommands(
  commands: ServiceRunCommand[],
  effects: ServiceRunCommandEffects,
): void {
  for (const command of commands) {
    if (command.type === "setActionLoading") {
      effects.dispatch(
        explorerActions.setActionStates((prevStates) => ({
          ...prevStates,
          [command.key]: "loading",
        })),
      );
    } else if (command.type === "setServiceLog") {
      effects.dispatch(
        explorerActions.setServiceLogs((prevLogs) => ({
          ...prevLogs,
          [command.key]: { lines: command.lines, ts: command.ts },
        })),
      );
    } else if (command.type === "completeServiceRun") {
      effects.dispatch(explorerActions.completeServiceRun(command.completion));
    } else if (command.type === "hydrateWorkspace") {
      effects.dispatch(
        explorerActions.hydrateWorkspace({
          virtualFiles: command.virtualFiles,
          workspaceReeFiles: command.workspaceReeFiles || [],
          ree: command.ree,
        }),
      );
    } else if (command.type === "persistFile") {
      effects.persistWorkspaceFile(command.path, command.content);
    } else if (command.type === "patchRee") {
      effects.dispatch(explorerActions.setRee((prevRee) => ({ ...prevRee, ...command.patch })));
    } else if (command.type === "setLocked") {
      effects.dispatch(explorerActions.setLocked(command.locked));
    } else {
      effects.showToast(command.message, command.toastType);
    }
  }
}

interface SourceCommandEffects {
  dispatch: ExplorerWorkflowDispatch;
  showToast: ShowToast;
}

export function executeSourceCommands(
  commands: SourceCommand[],
  effects: SourceCommandEffects,
): void {
  for (const command of commands) {
    if (command.type === "resetWorkflowOnSourceChange") {
      effects.dispatch(explorerActions.resetWorkflowOnSourceChange(command.serviceParams));
    } else if (command.type === "setSourceLoading") {
      effects.dispatch(
        explorerActions.setActionStates((prevStates) => ({ ...prevStates, source: "loading" })),
      );
    } else if (command.type === "hydrateWorkspace") {
      effects.dispatch(
        explorerActions.hydrateWorkspace({
          virtualFiles: command.virtualFiles,
          workspaceReeFiles: command.workspaceReeFiles || [],
          ree: command.ree,
        }),
      );
    } else if (command.type === "applySourceOutcome") {
      effects.dispatch(explorerActions.applySourceOutcome(command.outcome));
    } else if (command.type === "setSourceLog") {
      effects.dispatch(
        explorerActions.setServiceLogs((prevLogs) => ({
          ...prevLogs,
          source: { lines: command.lines, ts: command.ts },
        })),
      );
    } else {
      effects.showToast(command.message, command.toastType);
    }
  }
}
