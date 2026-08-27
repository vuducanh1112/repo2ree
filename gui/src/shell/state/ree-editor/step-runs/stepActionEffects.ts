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
  resetStepsAfterSourceChange,
  updateReeSpec,
} from "@shell/state/ree-editor/store/actions";
import type { AppShellAction } from "@shell/state/ree-editor/store/types";
import type { ShowToast } from "../types";

export type ReeEditorDispatch = (action: AppShellAction) => void;

interface EffectHandlers {
  dispatch: ReeEditorDispatch;
  persistWorkspaceFile: (path: string, content: string) => void;
  showToast: ShowToast;
}

function dispatchStateCommand(command: WorkspaceStateCommand, dispatch: ReeEditorDispatch): void {
  if (command.type === "setReeSpec") {
    dispatch(updateReeSpec(command.reeSpec));
    return;
  }

  if (command.type === "resetStepsAfterSourceChange") {
    dispatch(resetStepsAfterSourceChange(command.stepParams));
    return;
  }

  if (command.type === "applySourceOutcome") {
    dispatch(applySourceOutcome(command.outcome));
  }
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
