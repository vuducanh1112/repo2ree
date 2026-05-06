import {
  type AppShellEffect,
  mapAssemblyCommandsToEffects,
  mapSourceCommandsToEffects,
  type WorkspaceStateCommand,
} from "../../../application/ree-assembly/assemblyCommandEffects";
import type { AssemblyCommand } from "../../../application/ree-assembly/assemblyCommands";
import {
  applySourceOutcome,
  completeAssemblyRun,
  resetAssemblyAfterSourceChange,
  setActiveRunId,
  setArtifactStatus,
  setAssemblyRunLoading,
  setEvaluationState,
  setLocked,
  setWorkspaceSourceState,
  updateReeSpec,
} from "../../../application/state/actions";
import type { AppShellAction } from "../../../application/state/types";
import type { SourceCommand } from "../../../application/workspace/sourceAcquisitionCommands";
import type { ShowToast } from "../types";

export type ReeEditorDispatch = (action: AppShellAction) => void;

interface EffectHandlers {
  dispatch: ReeEditorDispatch;
  persistWorkspaceFile: (path: string, content: string) => void;
  showToast: ShowToast;
}

function dispatchStateCommand(command: WorkspaceStateCommand, dispatch: ReeEditorDispatch): void {
  if (command.type === "setAssemblyRunLoading") {
    dispatch(setAssemblyRunLoading(command.key));
    return;
  }

  if (command.type === "completeAssemblyRun") {
    dispatch(completeAssemblyRun(command.completion));
    return;
  }

  if (command.type === "setReeSpec") {
    dispatch(updateReeSpec(command.reeSpec));
    return;
  }

  if (command.type === "setWorkspaceSourceState") {
    dispatch(setWorkspaceSourceState(command.workspaceSourceState));
    return;
  }

  if (command.type === "setArtifactStatus") {
    dispatch(setArtifactStatus(command.artifactStatus));
    return;
  }

  if (command.type === "setEvaluationState") {
    dispatch(setEvaluationState(command.evaluationState));
    return;
  }

  if (command.type === "setActiveRunId") {
    dispatch(setActiveRunId(command.key, command.runId));
    return;
  }

  if (command.type === "setLocked") {
    dispatch(setLocked(command.locked));
    return;
  }

  if (command.type === "resetAssemblyAfterSourceChange") {
    dispatch(resetAssemblyAfterSourceChange(command.assemblyOperationParams));
    return;
  }

  dispatch(applySourceOutcome(command.outcome));
}

function executeEffects(effects: AppShellEffect[], handlers: EffectHandlers): void {
  for (const effect of effects) {
    if (effect.type === "dispatchStateCommand") {
      dispatchStateCommand(effect.command, handlers.dispatch);
      continue;
    }
    if (effect.type === "persistFile") {
      handlers.persistWorkspaceFile(effect.path, effect.content);
      continue;
    }
    handlers.showToast(effect.message, effect.toastType);
  }
}

export function executeAssemblyCommands(
  commands: AssemblyCommand[],
  handlers: EffectHandlers,
): void {
  executeEffects(mapAssemblyCommandsToEffects(commands), handlers);
}

export function executeSourceCommands(
  commands: SourceCommand[],
  effects: Pick<EffectHandlers, "dispatch" | "showToast">,
): void {
  executeEffects(mapSourceCommandsToEffects(commands), {
    ...effects,
    persistWorkspaceFile: () => {},
  });
}
