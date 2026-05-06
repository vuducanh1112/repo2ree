import type { ArtifactStatus } from "../../domain/artifact/ArtifactStatus";
import type { ReeSpec } from "../../domain/ree/ReeSpec";
import type { ReeAssemblyOperationParams } from "../../domain/ree/ReeTypes";
import type { EvaluationState } from "../../domain/review/EvaluationState";
import type { WorkspaceSourceState } from "../../domain/workspace/WorkspaceSourceState";
import type { ToastState } from "../ree-assembly/assemblyStepTypes";
import type {
  AppShellAction,
  AssemblyRunCompletionPayload,
  PatchAction,
  SliceName,
  SliceShape,
  SourceOutcomePayload,
  Updater,
} from "./types";

export const patch = <S extends SliceName>(
  slice: S,
  updater: Updater<Partial<SliceShape[S]>>,
): PatchAction =>
  ({
    type: "patch",
    slice,
    updater,
  }) as PatchAction;

export const applySourceOutcome = (outcome: SourceOutcomePayload): AppShellAction => ({
  type: "applySourceOutcome",
  outcome,
});

export const updateReeSpec = (value: Updater<ReeSpec>): AppShellAction => ({
  type: "updateReeSpec",
  value,
});

export const setWorkspaceSourceState = (value: Updater<WorkspaceSourceState>): AppShellAction => ({
  type: "setWorkspaceSourceState",
  value,
});

export const setArtifactStatus = (value: Updater<ArtifactStatus>): AppShellAction => ({
  type: "setArtifactStatus",
  value,
});

export const setEvaluationState = (value: Updater<EvaluationState>): AppShellAction => ({
  type: "setEvaluationState",
  value,
});

export const setAssemblyOperationParams = (
  value: Updater<ReeAssemblyOperationParams>,
): AppShellAction => ({
  type: "setAssemblyOperationParams",
  value,
});

export const setActiveRunId = (key: string, runId: string): AppShellAction => ({
  type: "setActiveRunId",
  key,
  runId,
});

export const setLocked = (locked: boolean): AppShellAction => ({
  type: "setLocked",
  locked,
});

export const setRepoMode = (repoMode: "url" | "upload"): AppShellAction => ({
  type: "setRepoMode",
  repoMode,
});

export const setAssemblyRunLoading = (key: string): AppShellAction => ({
  type: "setAssemblyRunLoading",
  key,
});

export const completeAssemblyRun = (completion: AssemblyRunCompletionPayload): AppShellAction => ({
  type: "completeAssemblyRun",
  completion,
});

export const resetAssemblyAfterSourceChange = (
  assemblyOperationParams: ReeAssemblyOperationParams,
): AppShellAction => ({
  type: "resetAssemblyAfterSourceChange",
  assemblyOperationParams,
});

export const showToast = (toast: ToastState): AppShellAction => ({
  type: "showToast",
  toast,
});

export const clearToast = (): AppShellAction => ({
  type: "clearToast",
});
