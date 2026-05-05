import type { ArtifactStatus } from "../../domain/artifact/ArtifactStatus";
import type { ReeSpec } from "../../domain/ree/ReeSpec";
import type { ActionStates } from "../../domain/ree/ReeTypes";
import type { EvaluationState } from "../../domain/review/EvaluationState";
import type { WorkspaceSourceState } from "../../domain/workspace/WorkspaceSourceState";
import type { ReeEditorViewModel } from "../ree-editor/reeEditorViewModel";
import type { Updater } from "../state/types";
import type { SourceCommand } from "../workspace/sourceAcquisitionCommands";
import type { AssemblyCommand } from "./assemblyCommands";

type SourceResetCommand = Extract<SourceCommand, { type: "resetWorkflowOnSourceChange" }>;
type SourceApplyOutcomeCommand = Extract<SourceCommand, { type: "applySourceOutcome" }>;

export type WorkspaceStateCommand =
  | {
      type: "setActionStates";
      actionStates: Updater<ActionStates>;
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

export function mapAssemblyCommandsToEffects(commands: AssemblyCommand[]): AppShellEffect[] {
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
    if (command.type === "setAssemblyRunLog") {
      // Logs are now served from React Query; drop this command.
      continue;
    }
    if (command.type === "completeAssemblyRun") {
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
      const patch = command.patch as Partial<ReeEditorViewModel>;
      const reeSpec: Partial<ReeSpec> = {};
      const workspaceSourceState: Partial<WorkspaceSourceState> = {};
      const artifactStatus: Partial<ArtifactStatus> = {};
      let evaluationState: EvaluationState | undefined;
      if (Object.hasOwn(patch, "name")) reeSpec.name = patch.name;
      if (Object.hasOwn(patch, "origin_url")) reeSpec.origin_url = patch.origin_url;
      if (Object.hasOwn(patch, "source_type")) reeSpec.source_type = patch.source_type;
      if (Object.hasOwn(patch, "runtime")) reeSpec.runtime = patch.runtime;
      if (Object.hasOwn(patch, "build_runtime_script"))
        reeSpec.build_runtime_script = patch.build_runtime_script;
      if (Object.hasOwn(patch, "activation_script"))
        reeSpec.activation_script = patch.activation_script;
      if (Object.hasOwn(patch, "sbom")) reeSpec.sbom = patch.sbom;
      if (Object.hasOwn(patch, "swhid")) reeSpec.swhid = patch.swhid;
      if (Object.hasOwn(patch, "zenodo_doi")) reeSpec.zenodo_doi = patch.zenodo_doi;
      if (Object.hasOwn(patch, "dataverse_doi")) reeSpec.dataverse_doi = patch.dataverse_doi;
      if (Object.hasOwn(patch, "repro_level")) reeSpec.repro_level = patch.repro_level;
      if (Object.hasOwn(patch, "detected_dependencies"))
        reeSpec.detected_dependencies = patch.detected_dependencies;
      if (Object.hasOwn(patch, "hardware_description"))
        reeSpec.hardware_description = patch.hardware_description;
      if (Object.hasOwn(patch, "sourceAvailable"))
        workspaceSourceState.sourceAvailable = patch.sourceAvailable;
      if (Object.hasOwn(patch, "sourceIncluded"))
        workspaceSourceState.sourceIncluded = patch.sourceIncluded;
      if (Object.hasOwn(patch, "sourceAcquiredBy"))
        workspaceSourceState.sourceAcquiredBy = patch.sourceAcquiredBy;
      if (Object.hasOwn(patch, "uploadedArchive"))
        workspaceSourceState.uploadedArchive = patch.uploadedArchive;
      if (Object.hasOwn(patch, "sourceSnapshotArchive"))
        workspaceSourceState.sourceSnapshotArchive = patch.sourceSnapshotArchive;
      if (Object.hasOwn(patch, "sourceSnapshotCapturedAt"))
        workspaceSourceState.sourceSnapshotCapturedAt = patch.sourceSnapshotCapturedAt;
      if (Object.hasOwn(patch, "runtimeIncluded"))
        artifactStatus.runtimeIncluded = patch.runtimeIncluded;
      if (Object.hasOwn(patch, "downloadableFiles"))
        artifactStatus.downloadableFiles = patch.downloadableFiles;
      if (Object.hasOwn(patch, "sealedAt")) artifactStatus.sealedAt = patch.sealedAt;
      if (Object.hasOwn(patch, "sealHash")) artifactStatus.sealHash = patch.sealHash;
      if (Object.hasOwn(patch, "evalLevel")) evaluationState = { evalLevel: patch.evalLevel ?? 0 };

      if (Object.keys(reeSpec).length > 0) {
        effects.push({
          type: "dispatchStateCommand",
          command: {
            type: "setReeSpec",
            reeSpec: (prevReeSpec) => ({ ...prevReeSpec, ...reeSpec }),
          },
        });
      }
      if (Object.keys(workspaceSourceState).length > 0) {
        effects.push({
          type: "dispatchStateCommand",
          command: {
            type: "setWorkspaceSourceState",
            workspaceSourceState: (prevState) => ({ ...prevState, ...workspaceSourceState }),
          },
        });
      }
      if (Object.keys(artifactStatus).length > 0) {
        effects.push({
          type: "dispatchStateCommand",
          command: {
            type: "setArtifactStatus",
            artifactStatus: (prevStatus) => ({ ...prevStatus, ...artifactStatus }),
          },
        });
      }
      if (evaluationState) {
        effects.push({
          type: "dispatchStateCommand",
          command: {
            type: "setEvaluationState",
            evaluationState: (prevState) => ({ ...prevState, ...evaluationState }),
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
