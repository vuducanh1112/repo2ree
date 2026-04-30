import type { ArtifactStatus } from "../../domain/artifact/ArtifactStatus";
import type { ReeDraftViewModel, ReeSpec } from "../../domain/ree/ReeSpec";
import type { ActionStates, WorkflowLogs } from "../../domain/ree/ReeTypes";
import { splitReePatch } from "../../domain/ree/reeDraftViewModel";
import type { EvaluationState } from "../../domain/review/EvaluationState";
import type { WorkspaceSourceState } from "../../domain/workspace/WorkspaceSourceState";
import type { WorkflowStepCommand } from "../workflow/workflowStepCommands";
import type { SourceCommand } from "./sourceAcquisitionCommands";

type SourceHydrationCommand = Extract<SourceCommand, { type: "hydrateWorkspace" }>;
type SourceResetCommand = Extract<SourceCommand, { type: "resetWorkflowOnSourceChange" }>;
type SourceApplyOutcomeCommand = Extract<SourceCommand, { type: "applySourceOutcome" }>;
type WorkflowRunCompletionCommand = Extract<WorkflowStepCommand, { type: "completeWorkflowRun" }>;
type WorkflowRunHydrationCommand = Extract<WorkflowStepCommand, { type: "hydrateWorkspace" }>;

export type WorkspaceStateCommand =
  | {
      type: "setActionStates";
      actionStates: (prevStates: ActionStates) => ActionStates;
    }
  | {
      type: "setWorkflowLogs";
      workflowLogs: (prevLogs: WorkflowLogs) => WorkflowLogs;
    }
  | {
      type: "completeWorkflowRun";
      completion: WorkflowRunCompletionCommand["completion"];
    }
  | {
      type: "hydrateWorkspace";
      workspace: {
        workspaceFiles:
          | WorkflowRunHydrationCommand["workspaceFiles"]
          | SourceHydrationCommand["workspaceFiles"];
        reeArtifactFiles:
          | NonNullable<WorkflowRunHydrationCommand["reeArtifactFiles"]>
          | NonNullable<SourceHydrationCommand["reeArtifactFiles"]>;
        reeSpec?: WorkflowRunHydrationCommand["reeSpec"] | SourceHydrationCommand["reeSpec"];
        workspaceSourceState?:
          | WorkflowRunHydrationCommand["workspaceSourceState"]
          | SourceHydrationCommand["workspaceSourceState"];
        artifactStatus?:
          | WorkflowRunHydrationCommand["artifactStatus"]
          | SourceHydrationCommand["artifactStatus"];
        evaluationState?:
          | WorkflowRunHydrationCommand["evaluationState"]
          | SourceHydrationCommand["evaluationState"];
      };
    }
  | { type: "setRee"; ree: (prevRee: ReeDraftViewModel) => ReeDraftViewModel }
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
  | { type: "setLocked"; locked: boolean }
  | {
      type: "resetWorkflowOnSourceChange";
      workflowParams: SourceResetCommand["workflowParams"];
    }
  | {
      type: "applySourceOutcome";
      outcome: SourceApplyOutcomeCommand["outcome"];
    };

export type WorkspaceShellEffect =
  | { type: "dispatchStateCommand"; command: WorkspaceStateCommand }
  | { type: "persistFile"; path: string; content: string }
  | { type: "toast"; message: string; toastType: "info" | "success" | "error" };

export function mapWorkflowStepCommandsToEffects(
  commands: WorkflowStepCommand[],
): WorkspaceShellEffect[] {
  const effects: WorkspaceShellEffect[] = [];

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
      effects.push({
        type: "dispatchStateCommand",
        command: {
          type: "setWorkflowLogs",
          workflowLogs: (prevLogs: WorkflowLogs) => ({
            ...prevLogs,
            [command.key]: { lines: command.lines, ts: command.ts },
          }),
        },
      });
      continue;
    }
    if (command.type === "completeWorkflowRun") {
      effects.push({
        type: "dispatchStateCommand",
        command: {
          type: "completeWorkflowRun",
          completion: command.completion,
        },
      });
      continue;
    }
    if (command.type === "hydrateWorkspace") {
      effects.push({
        type: "dispatchStateCommand",
        command: {
          type: "hydrateWorkspace",
          workspace: {
            workspaceFiles: command.workspaceFiles,
            reeArtifactFiles: command.reeArtifactFiles || [],
            reeSpec: command.reeSpec,
            workspaceSourceState: command.workspaceSourceState,
            artifactStatus: command.artifactStatus,
            evaluationState: command.evaluationState,
          },
        },
      });
      continue;
    }
    if (command.type === "patchRee") {
      const split = splitReePatch(command.patch);
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

export function mapSourceCommandsToEffects(commands: SourceCommand[]): WorkspaceShellEffect[] {
  return commands.map((command) => {
    if (command.type === "toast") {
      return {
        type: "toast",
        message: command.message,
        toastType: command.toastType,
      };
    }
    if (command.type === "setSourceLoading") {
      return {
        type: "dispatchStateCommand",
        command: {
          type: "setActionStates",
          actionStates: (prevStates) => ({
            ...prevStates,
            source: "loading",
          }),
        },
      };
    }
    if (command.type === "setSourceLog") {
      return {
        type: "dispatchStateCommand",
        command: {
          type: "setWorkflowLogs",
          workflowLogs: (prevLogs) => ({
            ...prevLogs,
            source: { lines: command.lines, ts: command.ts },
          }),
        },
      };
    }
    if (command.type === "resetWorkflowOnSourceChange") {
      return {
        type: "dispatchStateCommand",
        command: {
          type: "resetWorkflowOnSourceChange",
          workflowParams: command.workflowParams,
        },
      };
    }
    if (command.type === "applySourceOutcome") {
      return {
        type: "dispatchStateCommand",
        command: {
          type: "applySourceOutcome",
          outcome: command.outcome,
        },
      };
    }
    const hydrationCommand = command as SourceHydrationCommand;
    return {
      type: "dispatchStateCommand",
      command: {
        type: "hydrateWorkspace",
        workspace: {
          workspaceFiles: hydrationCommand.workspaceFiles,
          reeArtifactFiles: hydrationCommand.reeArtifactFiles || [],
          reeSpec: hydrationCommand.reeSpec,
          workspaceSourceState: hydrationCommand.workspaceSourceState,
          artifactStatus: hydrationCommand.artifactStatus,
          evaluationState: hydrationCommand.evaluationState,
        },
      },
    };
  });
}
