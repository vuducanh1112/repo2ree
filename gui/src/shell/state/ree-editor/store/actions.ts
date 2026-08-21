import type { ArtifactStatus } from "@core/artifact/ArtifactStatus";
import type { EvaluationState } from "@core/evaluate/EvaluationState";
import type { ReeSpec } from "@core/ree/ReeSpec";
import type { ReeStepParams } from "@core/ree/ReeTypes";
import type { ToastState } from "@core/ree-steps/stepTypes";
import type { WorkspaceSourceState } from "@core/workspace/WorkspaceSourceState";
import type {
  AppShellAction,
  PatchAction,
  SliceName,
  SliceShape,
  SourceOutcomePayload,
  StepRunCompletionPayload,
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

export const setStepParams = (value: Updater<ReeStepParams>): AppShellAction => ({
  type: "setStepParams",
  value,
});

export const setActiveRunId = (key: string, runId: string): AppShellAction => ({
  type: "setActiveRunId",
  key,
  runId,
});

export const cancelStepRun = (key: string, runId?: string): AppShellAction => ({
  type: "cancelStepRun",
  key,
  runId,
});

export const setLocked = (value: Updater<boolean>): AppShellAction => ({
  type: "setLocked",
  value,
});

export const setRepoMode = (value: Updater<"url" | "upload">): AppShellAction => ({
  type: "setRepoMode",
  value,
});

export const setFocusedField = (value: Updater<string | null>): AppShellAction => ({
  type: "setFocusedField",
  value,
});

export const setStepRunLoading = (key: string): AppShellAction => ({
  type: "setStepRunLoading",
  key,
});

export const completeStepRun = (completion: StepRunCompletionPayload): AppShellAction => ({
  type: "completeStepRun",
  completion,
});

export const resetStepsAfterSourceChange = (stepParams: ReeStepParams): AppShellAction => ({
  type: "resetStepsAfterSourceChange",
  stepParams,
});

export const showToast = (toast: ToastState): AppShellAction => ({
  type: "showToast",
  toast,
});

export const clearToast = (): AppShellAction => ({
  type: "clearToast",
});
