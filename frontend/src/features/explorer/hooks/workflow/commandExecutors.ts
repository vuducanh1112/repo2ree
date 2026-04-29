import {
  type ExplorerShellEffect,
  type ExplorerStateCommand,
  mapServiceRunCommandsToEffects,
  mapSourceCommandsToEffects,
} from "../../../../application/explorer/explorerShellEffects";
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

function dispatchExplorerStateCommand(
  command: ExplorerStateCommand,
  dispatch: ExplorerWorkflowDispatch,
): void {
  if (command.type === "setActionStates") {
    dispatch(explorerActions.setActionStates(command.actionStates));
  } else if (command.type === "setServiceLogs") {
    dispatch(explorerActions.setServiceLogs(command.serviceLogs));
  } else if (command.type === "completeServiceRun") {
    dispatch(explorerActions.completeServiceRun(command.completion));
  } else if (command.type === "hydrateWorkspace") {
    dispatch(explorerActions.hydrateWorkspace(command.workspace));
  } else if (command.type === "setRee") {
    dispatch(explorerActions.setRee(command.ree));
  } else if (command.type === "setLocked") {
    dispatch(explorerActions.setLocked(command.locked));
  } else if (command.type === "resetWorkflowOnSourceChange") {
    dispatch(explorerActions.resetWorkflowOnSourceChange(command.serviceParams));
  } else {
    dispatch(explorerActions.applySourcePatchOutcome(command.outcome));
  }
}

function executeExplorerEffects(
  effects: ExplorerShellEffect[],
  handlers: ServiceRunCommandEffects,
): void {
  for (const effect of effects) {
    if (effect.type === "dispatchStateCommand") {
      dispatchExplorerStateCommand(effect.command, handlers.dispatch);
    } else if (effect.type === "persistFile") {
      handlers.persistWorkspaceFile(effect.path, effect.content);
    } else {
      handlers.showToast(effect.message, effect.toastType);
    }
  }
}

export function executeServiceRunCommands(
  commands: ServiceRunCommand[],
  effects: ServiceRunCommandEffects,
): void {
  executeExplorerEffects(mapServiceRunCommandsToEffects(commands), effects);
}

interface SourceCommandEffects {
  dispatch: ExplorerWorkflowDispatch;
  showToast: ShowToast;
}

export function executeSourceCommands(
  commands: SourceCommand[],
  effects: SourceCommandEffects,
): void {
  executeExplorerEffects(mapSourceCommandsToEffects(commands), {
    ...effects,
    persistWorkspaceFile: () => {},
  });
}
