import type { ArtifactStatus } from "../../domain/artifact/ArtifactStatus";
import type { ReeSpec } from "../../domain/ree/ReeSpec";
import type { ActionStates } from "../../domain/ree/ReeTypes";
import { splitReeViewPatch } from "../../domain/ree/ReeViewState";
import type { EvaluationState } from "../../domain/review/EvaluationState";
import type { WorkspaceSourceState } from "../../domain/workspace/WorkspaceSourceState";
import type { WorkflowStepCommand } from "../workflow/workflowStepCommands";
import type { SourceCommand } from "./sourceAcquisitionCommands";

type SourceResetCommand = Extract<SourceCommand, { type: "resetWorkflowOnSourceChange" }>;
type SourceApplyOutcomeCommand = Extract<SourceCommand, { type: "applySourceOutcome" }>;

export type WorkspaceStateCommand =
  | {
      type: "setActionStates";
      actionStates: (prevStates: ActionStates) => ActionStates;
    }
  | {
      type: "completeWorkflowRun";
      completion: {
        key: string;
        actionState: "done";
        badge: boolean;
        timestamp: string;
      };
    }
  | {
      type: "setReeSpec";
      reeSpec: (prevReeSpec: ReeSpec) => ReeSpec;
    }
  | {
      type: "setWorkspaceSourceState";
      workspaceSourceState: (prevState: WorkspaceSourceState) => WorkspaceSourceState;
    }
  | {
      type: "setArtifactStatus";
      artifactStatus: (prevStatus: ArtifactStatus) => ArtifactStatus;
    }
  | {
      type: "setEvaluationState";
      evaluationState: (prevState: EvaluationState) => EvaluationState;
    }
  | { type: "setActiveRunId"; key: string; runId: string }
  | { type: "setLocked"; locked: boolean }
  | {
      type: "resetWorkflowOnSourceChange";
      workflowParams: SourceResetCommand["workflowParams"];
    }
  | {
      type: "applySourceOutcome";
      outcome: SourceApplyOutcomeCommand["outcome"];
    };

export type AppShellEffect =
  | { type: "dispatchStateCommand"; command: WorkspaceStateCommand }
  | { type: "persistFile"; path: string; content: string }
  | { type: "toast"; message: string; toastType: "info" | "success" | "error" };

export function mapWorkflowStepCommandsToEffects(
  commands: WorkflowStepCommand[],
): AppShellEffect[] {
  const effects: AppShellEffect[] = [];

  for (const command of commands) {
    if (command.type === "persistFile") {
      effects.push({
        type: "persistFile",
        path: command.path,
        content: command.content,
      });
      continue;
    }
    if (command.type === "toast") {
      effects.push({
        type: "toast",
        message: command.message,
        toastType: command.toastType,
      });
      continue;
    }
    if (command.type === "setActionLoading") {
      effects.push({
        type: "dispatchStateCommand",
        command: {
          type: "setActionStates",
          actionStates: (prevStates: ActionStates) => ({
            ...prevStates,
            [command.key]: "loading",
          }),
        },
      });
      continue;
    }
    if (command.type === "setWorkflowRunLog") {
      // Logs are now served from React Query; drop this command.
      continue;
    }
    if (command.type === "completeWorkflowRun") {
      effects.push({
        type: "dispatchStateCommand",
        command: {
          type: "completeWorkflowRun",
          completion: {
            key: command.completion.key,
            actionState: command.completion.actionState,
            badge: command.completion.badge,
            timestamp: command.completion.timestamp,
          },
        },
      });
      continue;
    }
    if (command.type === "setActiveRunId") {
      effects.push({
        type: "dispatchStateCommand",
        command: {
          type: "setActiveRunId",
          key: command.key,
          runId: command.runId,
        },
      });
      continue;
    }
    if (command.type === "hydrateWorkspace") {
      // Workspace files now come from React Query; only persist reeSpec/source state updates.
      if (command.reeSpec) {
        const reeSpec = command.reeSpec;
        effects.push({
          type: "dispatchStateCommand",
          command: {
            type: "setReeSpec",
            reeSpec: () => reeSpec,
          },
        });
      }
      if (command.workspaceSourceState) {
        effects.push({
          type: "dispatchStateCommand",
          command: {
            type: "setWorkspaceSourceState",
            workspaceSourceState: (prevState) => ({
              ...prevState,
              ...command.workspaceSourceState,
            }),
          },
        });
      }
      if (command.artifactStatus) {
        effects.push({
          type: "dispatchStateCommand",
          command: {
            type: "setArtifactStatus",
            artifactStatus: (prevStatus) => ({ ...prevStatus, ...command.artifactStatus }),
          },
        });
      }
      if (command.evaluationState) {
        effects.push({
          type: "dispatchStateCommand",
          command: {
            type: "setEvaluationState",
            evaluationState: (prevState) => ({ ...prevState, ...command.evaluationState }),
          },
        });
      }
      continue;
    }
    if (command.type === "patchRee") {
      const split = splitReeViewPatch(command.patch);
      if (split.reeSpec) {
        effects.push({
          type: "dispatchStateCommand",
          command: {
            type: "setReeSpec",
            reeSpec: (prevReeSpec) => ({ ...prevReeSpec, ...split.reeSpec }),
          },
        });
      }
      if (split.workspaceSourceState) {
        effects.push({
          type: "dispatchStateCommand",
          command: {
            type: "setWorkspaceSourceState",
            workspaceSourceState: (prevState) => ({ ...prevState, ...split.workspaceSourceState }),
          },
        });
      }
      if (split.artifactStatus) {
        effects.push({
          type: "dispatchStateCommand",
          command: {
            type: "setArtifactStatus",
            artifactStatus: (prevStatus) => ({ ...prevStatus, ...split.artifactStatus }),
          },
        });
      }
      if (split.evaluationState) {
        effects.push({
          type: "dispatchStateCommand",
          command: {
            type: "setEvaluationState",
            evaluationState: (prevState) => ({ ...prevState, ...split.evaluationState }),
          },
        });
      }
      continue;
    }

    effects.push({
      type: "dispatchStateCommand",
      command: {
        type: "setLocked",
        locked: command.locked,
      },
    });
  }

  return effects;
}

export function mapSourceCommandsToEffects(commands: SourceCommand[]): AppShellEffect[] {
  return commands.flatMap((command) => {
    if (command.type === "toast") {
      return [
        {
          type: "toast" as const,
          message: command.message,
          toastType: command.toastType,
        },
      ];
    }
    if (command.type === "setSourceLoading") {
      return [
        {
          type: "dispatchStateCommand" as const,
          command: {
            type: "setActionStates" as const,
            actionStates: (prevStates: ActionStates) => ({
              ...prevStates,
              source: "loading" as const,
            }),
          },
        },
      ];
    }
    if (command.type === "setSourceLog") {
      // Logs are now served from React Query; drop this command.
      return [];
    }
    if (command.type === "setActiveRunId") {
      return [
        {
          type: "dispatchStateCommand" as const,
          command: {
            type: "setActiveRunId" as const,
            key: command.key,
            runId: command.runId,
          },
        },
      ];
    }
    if (command.type === "resetWorkflowOnSourceChange") {
      return [
        {
          type: "dispatchStateCommand" as const,
          command: {
            type: "resetWorkflowOnSourceChange" as const,
            workflowParams: command.workflowParams,
          },
        },
      ];
    }
    if (command.type === "applySourceOutcome") {
      return [
        {
          type: "dispatchStateCommand" as const,
          command: {
            type: "applySourceOutcome" as const,
            outcome: command.outcome,
          },
        },
      ];
    }
    if (command.type === "hydrateWorkspace") {
      // Workspace files now come from React Query; only persist state changes.
      const hydrateEffects: AppShellEffect[] = [];
      if (command.reeSpec) {
        const reeSpec = command.reeSpec;
        hydrateEffects.push({
          type: "dispatchStateCommand",
          command: {
            type: "setReeSpec",
            reeSpec: () => reeSpec,
          },
        });
      }
      if (command.workspaceSourceState) {
        hydrateEffects.push({
          type: "dispatchStateCommand",
          command: {
            type: "setWorkspaceSourceState",
            workspaceSourceState: (prevState) => ({
              ...prevState,
              ...command.workspaceSourceState,
            }),
          },
        });
      }
      if (command.artifactStatus) {
        hydrateEffects.push({
          type: "dispatchStateCommand",
          command: {
            type: "setArtifactStatus",
            artifactStatus: (prevStatus) => ({ ...prevStatus, ...command.artifactStatus }),
          },
        });
      }
      if (command.evaluationState) {
        hydrateEffects.push({
          type: "dispatchStateCommand",
          command: {
            type: "setEvaluationState",
            evaluationState: (prevState) => ({ ...prevState, ...command.evaluationState }),
          },
        });
      }
      return hydrateEffects;
    }
    return [];
  });
}
