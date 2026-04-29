import {
  type ExplorerShellEffect,
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

function executeExplorerEffects(
  effects: ExplorerShellEffect[],
  handlers: ServiceRunCommandEffects,
): void {
  for (const effect of effects) {
    if (effect.type === "setActionLoading") {
      handlers.dispatch(
        explorerActions.setActionStates((prevStates) => ({
          ...prevStates,
          [effect.key]: "loading",
        })),
      );
    } else if (effect.type === "setServiceLog") {
      handlers.dispatch(
        explorerActions.setServiceLogs((prevLogs) => ({
          ...prevLogs,
          [effect.key]: { lines: effect.lines, ts: effect.ts },
        })),
      );
    } else if (effect.type === "completeServiceRun") {
      handlers.dispatch(explorerActions.completeServiceRun(effect.completion));
    } else if (effect.type === "hydrateWorkspace") {
      handlers.dispatch(
        explorerActions.hydrateWorkspace({
          virtualFiles: effect.virtualFiles,
          workspaceReeFiles: effect.workspaceReeFiles || [],
          ree: effect.ree,
        }),
      );
    } else if (effect.type === "persistFile") {
      handlers.persistWorkspaceFile(effect.path, effect.content);
    } else if (effect.type === "patchRee") {
      handlers.dispatch(explorerActions.setRee((prevRee) => ({ ...prevRee, ...effect.patch })));
    } else if (effect.type === "setLocked") {
      handlers.dispatch(explorerActions.setLocked(effect.locked));
    } else if (effect.type === "resetWorkflowOnSourceChange") {
      handlers.dispatch(explorerActions.resetWorkflowOnSourceChange(effect.serviceParams));
    } else if (effect.type === "applySourceOutcome") {
      handlers.dispatch(explorerActions.applySourceOutcome(effect.outcome));
    } else if (effect.type === "setSourceLog") {
      handlers.dispatch(
        explorerActions.setServiceLogs((prevLogs) => ({
          ...prevLogs,
          source: { lines: effect.lines, ts: effect.ts },
        })),
      );
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
