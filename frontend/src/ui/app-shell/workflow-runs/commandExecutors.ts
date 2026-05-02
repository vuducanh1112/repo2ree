import type { AppShellAction } from "../../../application/app-shell";
import { appShellActions } from "../../../application/app-shell";
import type { WorkflowStepCommand } from "../../../application/workflow/workflowStepCommands";
import type { SourceCommand } from "../../../application/workspace/sourceAcquisitionCommands";
import {
  type AppShellEffect,
  mapSourceCommandsToEffects,
  mapWorkflowStepCommandsToEffects,
  type WorkspaceStateCommand,
} from "../../../application/workspace/workspaceMutationEffects";
import type { ShowToast } from "./types";

export type WorkspaceWorkflowDispatch = (action: AppShellAction) => void;

interface WorkflowStepCommandEffects {
  dispatch: WorkspaceWorkflowDispatch;
  persistWorkspaceFile: (path: string, content: string) => void;
  showToast: ShowToast;
}

function dispatchWorkspaceStateCommand(
  command: WorkspaceStateCommand,
  dispatch: WorkspaceWorkflowDispatch,
): void {
  if (command.type === "setActionStates") {
    dispatch(appShellActions.setActionStates(command.actionStates));
  } else if (command.type === "setWorkflowLogs") {
    dispatch(appShellActions.setWorkflowLogs(command.workflowLogs));
  } else if (command.type === "completeWorkflowRun") {
    dispatch(appShellActions.completeWorkflowRun(command.completion));
  } else if (command.type === "hydrateWorkspace") {
    dispatch(appShellActions.hydrateWorkspace(command.workspace));
  } else if (command.type === "setRee") {
    dispatch(appShellActions.setRee(command.ree));
  } else if (command.type === "setReeSpec") {
    dispatch(appShellActions.setReeSpec(command.reeSpec));
  } else if (command.type === "setWorkspaceSourceState") {
    dispatch(appShellActions.setWorkspaceSourceState(command.workspaceSourceState));
  } else if (command.type === "setArtifactStatus") {
    dispatch(appShellActions.setArtifactStatus(command.artifactStatus));
  } else if (command.type === "setEvaluationState") {
    dispatch(appShellActions.setEvaluationState(command.evaluationState));
  } else if (command.type === "setLocked") {
    dispatch(appShellActions.setLocked(command.locked));
  } else if (command.type === "resetWorkflowOnSourceChange") {
    dispatch(appShellActions.resetWorkflowOnSourceChange(command.workflowParams));
  } else {
    dispatch(appShellActions.applySourceOutcome(command.outcome));
  }
}

function executeWorkspaceEffects(
  effects: AppShellEffect[],
  handlers: WorkflowStepCommandEffects,
): void {
  for (const effect of effects) {
    if (effect.type === "dispatchStateCommand") {
      dispatchWorkspaceStateCommand(effect.command, handlers.dispatch);
    } else if (effect.type === "persistFile") {
      handlers.persistWorkspaceFile(effect.path, effect.content);
    } else {
      handlers.showToast(effect.message, effect.toastType);
    }
  }
}

export function executeWorkflowStepCommands(
  commands: WorkflowStepCommand[],
  effects: WorkflowStepCommandEffects,
): void {
  executeWorkspaceEffects(mapWorkflowStepCommandsToEffects(commands), effects);
}

interface SourceCommandEffects {
  dispatch: WorkspaceWorkflowDispatch;
  showToast: ShowToast;
}

export function executeSourceCommands(
  commands: SourceCommand[],
  effects: SourceCommandEffects,
): void {
  executeWorkspaceEffects(mapSourceCommandsToEffects(commands), {
    ...effects,
    persistWorkspaceFile: () => {},
  });
}
