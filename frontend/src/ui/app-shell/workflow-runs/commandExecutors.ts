import type { AppShellAction } from "../../../application/app-shell/AppShellTypes";
import {
  applySourceOutcome,
  completeWorkflowRun,
  patch,
  resetWorkflowOnSourceChange,
} from "../../../application/state/actions";
import { resolveUpdater } from "../../../application/state/types";
import type { WorkflowStepCommand } from "../../../application/workflow/workflowStepCommands";
import type { SourceCommand } from "../../../application/workspace/sourceAcquisitionCommands";
import {
  type AppShellEffect,
  mapSourceCommandsToEffects,
  mapWorkflowStepCommandsToEffects,
  type WorkspaceStateCommand,
} from "../../../application/workspace/workspaceMutationEffects";
import type { ArtifactStatus } from "../../../domain/artifact/ArtifactStatus";
import type { ReeSpec } from "../../../domain/ree/ReeSpec";
import type { ActionStates } from "../../../domain/ree/ReeTypes";
import type { EvaluationState } from "../../../domain/review/EvaluationState";
import type { WorkspaceSourceState } from "../../../domain/workspace/WorkspaceSourceState";
import type { ShowToast } from "./types";

export type WorkspaceWorkflowDispatch = (action: AppShellAction) => void;

interface WorkflowStepCommandEffects {
  dispatch: WorkspaceWorkflowDispatch;
  persistWorkspaceFile: (path: string, content: string) => void;
  showToast: ShowToast;
}

function dispatchReeStateCommand(
  command: WorkspaceStateCommand,
  dispatch: WorkspaceWorkflowDispatch,
): void {
  if (command.type === "setActionStates") {
    dispatch(
      patch("workflowRun", (prev) => ({
        actionStates: resolveUpdater(prev.actionStates as ActionStates, command.actionStates),
      })),
    );
  } else if (command.type === "completeWorkflowRun") {
    dispatch(completeWorkflowRun(command.completion));
  } else if (command.type === "setReeSpec") {
    dispatch(
      patch("reeDraft", (prev) => ({
        reeSpec: resolveUpdater(prev.reeSpec as ReeSpec, command.reeSpec),
      })),
    );
  } else if (command.type === "setWorkspaceSourceState") {
    dispatch(
      patch("reeDraft", (prev) => ({
        workspaceSourceState: resolveUpdater(
          prev.workspaceSourceState as WorkspaceSourceState,
          command.workspaceSourceState,
        ),
      })),
    );
  } else if (command.type === "setArtifactStatus") {
    dispatch(
      patch("reeDraft", (prev) => ({
        artifactStatus: resolveUpdater(
          prev.artifactStatus as ArtifactStatus,
          command.artifactStatus,
        ),
      })),
    );
  } else if (command.type === "setEvaluationState") {
    dispatch(
      patch("workflowRun", (prev) => ({
        evaluationState: resolveUpdater(
          prev.evaluationState as EvaluationState,
          command.evaluationState,
        ),
      })),
    );
  } else if (command.type === "setActiveRunId") {
    dispatch(
      patch("workflowRun", (prev) => ({
        activeRunIds: {
          ...prev.activeRunIds,
          [command.key]: command.runId,
        },
      })),
    );
  } else if (command.type === "setLocked") {
    dispatch(patch("reeDraft", { locked: command.locked }));
  } else if (command.type === "resetWorkflowOnSourceChange") {
    dispatch(resetWorkflowOnSourceChange(command.workflowParams));
  } else {
    dispatch(applySourceOutcome(command.outcome));
  }
}

function executeWorkspaceEffects(
  effects: AppShellEffect[],
  handlers: WorkflowStepCommandEffects,
): void {
  for (const effect of effects) {
    if (effect.type === "dispatchStateCommand") {
      dispatchReeStateCommand(effect.command, handlers.dispatch);
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
