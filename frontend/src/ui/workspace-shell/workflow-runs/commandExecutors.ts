import type { WorkflowStepCommand } from "../../../application/workflow/workflowStepCommands";
import type { SourceCommand } from "../../../application/workspace/sourceAcquisitionCommands";
import {
  mapSourceCommandsToEffects,
  mapWorkflowStepCommandsToEffects,
  type WorkspaceShellEffect,
  type WorkspaceStateCommand,
} from "../../../application/workspace/workspaceMutationEffects";
import type { WorkspaceShellAction } from "../../../application/workspace-shell";
import { workspaceShellActions } from "../../../application/workspace-shell";
import type { ShowToast } from "./types";

export type WorkspaceWorkflowDispatch = (action: WorkspaceShellAction) => void;

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
    dispatch(workspaceShellActions.setActionStates(command.actionStates));
  } else if (command.type === "setWorkflowLogs") {
    dispatch(workspaceShellActions.setWorkflowLogs(command.workflowLogs));
  } else if (command.type === "completeWorkflowRun") {
    dispatch(workspaceShellActions.completeWorkflowRun(command.completion));
  } else if (command.type === "hydrateWorkspace") {
    dispatch(workspaceShellActions.hydrateWorkspace(command.workspace));
  } else if (command.type === "setRee") {
    dispatch(workspaceShellActions.setRee(command.ree));
  } else if (command.type === "setLocked") {
    dispatch(workspaceShellActions.setLocked(command.locked));
  } else if (command.type === "resetWorkflowOnSourceChange") {
    dispatch(workspaceShellActions.resetWorkflowOnSourceChange(command.workflowParams));
  } else {
    dispatch(workspaceShellActions.applySourcePatchOutcome(command.outcome));
  }
}

function executeWorkspaceEffects(
  effects: WorkspaceShellEffect[],
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
