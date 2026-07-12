import {
  mapSourceCommandsToEffects,
  mapStepCommandsToEffects,
  type StepEffect,
  type WorkspaceStateCommand,
} from "@core/ree-steps/stepCommandEffects";
import type { StepCommand } from "@core/ree-steps/stepCommands";
import type { SourceCommand } from "@core/workspace/sourceAcquisitionCommands";
import {
  applySourceOutcome,
  completeStepRun,
  resetStepsAfterSourceChange,
  setActiveRunId,
  setArtifactStatus,
  setEvaluationState,
  setLocked,
  setStepRunLoading,
  setWorkspaceSourceState,
  updateReeSpec,
} from "@shell/ui/app-shell/state/actions";
import type { AppShellAction } from "@shell/ui/app-shell/state/types";
import type { ShowToast } from "../types";

export type ReeEditorDispatch = (action: AppShellAction) => void;

interface EffectHandlers {
  dispatch: ReeEditorDispatch;
  persistWorkspaceFile: (path: string, content: string) => void;
  showToast: ShowToast;
}

function dispatchStateCommand(command: WorkspaceStateCommand, dispatch: ReeEditorDispatch): void {
  if (command.type === "setStepRunLoading") {
    dispatch(setStepRunLoading(command.key));
    return;
  }

  if (command.type === "completeStepRun") {
    dispatch(completeStepRun(command.completion));
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

  if (command.type === "resetStepsAfterSourceChange") {
    dispatch(resetStepsAfterSourceChange(command.stepParams));
    return;
  }

  dispatch(applySourceOutcome(command.outcome));
}

function executeEffects(effects: StepEffect[], handlers: EffectHandlers): void {
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

export function executeStepCommands(commands: StepCommand[], handlers: EffectHandlers): void {
  executeEffects(mapStepCommandsToEffects(commands), handlers);
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
