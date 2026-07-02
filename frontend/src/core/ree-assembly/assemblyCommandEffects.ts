import type { ArtifactStatus } from "../artifact/ArtifactStatus";
import type { EvaluationState } from "../evaluate/EvaluationState";
import type { ReeSpec } from "../ree/ReeSpec";
import type { SourceCommand } from "../workspace/sourceAcquisitionCommands";
import type { WorkspaceSourceState } from "../workspace/WorkspaceSourceState";
import type { AssemblyCommand } from "./assemblyCommands";

type Updater<T> = T | ((previous: T) => T);

type SourceResetCommand = Extract<SourceCommand, { type: "resetAssemblyAfterSourceChange" }>;
type SourceApplyOutcomeCommand = Extract<SourceCommand, { type: "applySourceOutcome" }>;

export type WorkspaceStateCommand =
  | {
      type: "setAssemblyRunLoading";
      key: string;
    }
  | {
      type: "completeAssemblyRun";
      completion: {
        key: string;
        runId?: string;
        actionState: "done";
        badge: boolean;
        timestamp: string;
      };
    }
  | {
      type: "setReeSpec";
      reeSpec: Updater<ReeSpec>;
    }
  | {
      type: "setWorkspaceSourceState";
      workspaceSourceState: Updater<WorkspaceSourceState>;
    }
  | {
      type: "setArtifactStatus";
      artifactStatus: Updater<ArtifactStatus>;
    }
  | {
      type: "setEvaluationState";
      evaluationState: Updater<EvaluationState>;
    }
  | { type: "setActiveRunId"; key: string; runId: string }
  | { type: "setLocked"; locked: boolean }
  | {
      type: "resetAssemblyAfterSourceChange";
      assemblyOperationParams: SourceResetCommand["assemblyOperationParams"];
    }
  | {
      type: "applySourceOutcome";
      outcome: SourceApplyOutcomeCommand["outcome"];
    };

export type AssemblyEffect =
  | { type: "dispatchStateCommand"; command: WorkspaceStateCommand }
  | { type: "persistFile"; path: string; content: string }
  | { type: "toast"; message: string; toastType: "info" | "success" | "error" };

export function mapAssemblyCommandsToEffects(commands: AssemblyCommand[]): AssemblyEffect[] {
  const effects: AssemblyEffect[] = [];

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
          type: "setAssemblyRunLoading",
          key: command.key,
        },
      });
      continue;
    }
    if (command.type === "setAssemblyRunLog") {
      continue;
    }
    if (command.type === "completeAssemblyRun") {
      effects.push({
        type: "dispatchStateCommand",
        command: {
          type: "completeAssemblyRun",
          completion: {
            key: command.completion.key,
            runId: command.completion.runId,
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
    if (command.type === "setReeSpec") {
      const reeSpec = command.reeSpec;
      effects.push({
        type: "dispatchStateCommand",
        command: {
          type: "setReeSpec",
          reeSpec: (prev) => ({ ...prev, ...reeSpec }),
        },
      });
      continue;
    }
    if (command.type === "setArtifactStatus") {
      const artifactStatus = command.artifactStatus;
      effects.push({
        type: "dispatchStateCommand",
        command: {
          type: "setArtifactStatus",
          artifactStatus: (prev) => ({ ...prev, ...artifactStatus }),
        },
      });
      continue;
    }
    if (command.type === "setEvaluationState") {
      const evaluationState = command.evaluationState;
      effects.push({
        type: "dispatchStateCommand",
        command: {
          type: "setEvaluationState",
          evaluationState: (prev) => ({ ...prev, ...evaluationState }),
        },
      });
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

export function mapSourceCommandsToEffects(commands: SourceCommand[]): AssemblyEffect[] {
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
            type: "setAssemblyRunLoading" as const,
            key: "source",
          },
        },
      ];
    }
    if (command.type === "setSourceLog") {
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
    if (command.type === "resetAssemblyAfterSourceChange") {
      return [
        {
          type: "dispatchStateCommand" as const,
          command: {
            type: "resetAssemblyAfterSourceChange" as const,
            assemblyOperationParams: command.assemblyOperationParams,
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
      const hydrateEffects: AssemblyEffect[] = [];
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
