import {
  type AppShellEffect,
  mapAssemblyCommandsToEffects,
  mapSourceCommandsToEffects,
  type WorkspaceStateCommand,
} from "../../../application/ree-assembly/assemblyCommandEffects";
import type { AssemblyCommand } from "../../../application/ree-assembly/assemblyCommands";
import {
  applySourceOutcome,
  completeWorkflowRun,
  patch,
  resetWorkflowOnSourceChange,
} from "../../../application/state/actions";
import type { AppShellAction } from "../../../application/state/types";
import { resolveUpdater } from "../../../application/state/types";
import type { SourceCommand } from "../../../application/workspace/sourceAcquisitionCommands";
import type { ArtifactStatus } from "../../../domain/artifact/ArtifactStatus";
import type { ReeSpec } from "../../../domain/ree/ReeSpec";
import type { ActionStates } from "../../../domain/ree/ReeTypes";
import type { EvaluationState } from "../../../domain/review/EvaluationState";
import type { WorkspaceSourceState } from "../../../domain/workspace/WorkspaceSourceState";
import type { ShowToast } from "../types";

export type ReeEditorDispatch = (action: AppShellAction) => void;

interface EffectHandlers {
  dispatch: ReeEditorDispatch;
  persistWorkspaceFile: (path: string, content: string) => void;
  showToast: ShowToast;
}

function dispatchStateCommand(command: WorkspaceStateCommand, dispatch: ReeEditorDispatch): void {
  if (command.type === "setActionStates") {
    dispatch(
      patch("workflowRun", (prev) => ({
        actionStates: resolveUpdater(prev.actionStates as ActionStates, command.actionStates),
      })),
    );
    return;
  }

  if (command.type === "completeWorkflowRun") {
    dispatch(completeWorkflowRun(command.completion));
    return;
  }

  if (command.type === "setReeSpec") {
    dispatch(
      patch("reeDraft", (prev) => ({
        reeSpec: resolveUpdater(prev.reeSpec as ReeSpec, command.reeSpec),
      })),
    );
    return;
  }

  if (command.type === "setWorkspaceSourceState") {
    dispatch(
      patch("reeDraft", (prev) => ({
        workspaceSourceState: resolveUpdater(
          prev.workspaceSourceState as WorkspaceSourceState,
          command.workspaceSourceState,
        ),
      })),
    );
    return;
  }

  if (command.type === "setArtifactStatus") {
    dispatch(
      patch("reeDraft", (prev) => ({
        artifactStatus: resolveUpdater(
          prev.artifactStatus as ArtifactStatus,
          command.artifactStatus,
        ),
      })),
    );
    return;
  }

  if (command.type === "setEvaluationState") {
    dispatch(
      patch("workflowRun", (prev) => ({
        evaluationState: resolveUpdater(
          prev.evaluationState as EvaluationState,
          command.evaluationState,
        ),
      })),
    );
    return;
  }

  if (command.type === "setActiveRunId") {
    dispatch(
      patch("workflowRun", (prev) => ({
        activeRunIds: {
          ...prev.activeRunIds,
          [command.key]: command.runId,
        },
      })),
    );
    return;
  }

  if (command.type === "setLocked") {
    dispatch(patch("reeDraft", { locked: command.locked }));
    return;
  }

  if (command.type === "resetWorkflowOnSourceChange") {
    dispatch(resetWorkflowOnSourceChange(command.workflowParams));
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
