import type { ArtifactStatus } from "../../domain/artifact/ArtifactStatus";
import type { ReeSpec } from "../../domain/ree/ReeSpec";
import type { WorkflowParams } from "../../domain/ree/ReeTypes";
import type { EvaluationState } from "../../domain/review/EvaluationState";
import type { WorkspaceSourceState } from "../../domain/workspace/WorkspaceSourceState";
import type { ToastState } from "../workflow/WorkflowStepTypes";
import type {
  AppShellAction,
  PatchAction,
  SliceName,
  SliceShape,
  SourceOutcomePayload,
  Updater,
  WorkflowRunCompletionPayload,
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

export const setWorkflowParams = (value: Updater<WorkflowParams>): AppShellAction => ({
  type: "setWorkflowParams",
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

export const setAssemblyRunLoading = (key: string): AppShellAction => ({
  type: "setAssemblyRunLoading",
  key,
});

export const completeAssemblyRun = (completion: WorkflowRunCompletionPayload): AppShellAction => ({
  type: "completeAssemblyRun",
  completion,
});

export const resetAssemblyAfterSourceChange = (workflowParams: WorkflowParams): AppShellAction => ({
  type: "resetAssemblyAfterSourceChange",
  workflowParams,
});

export const showToast = (toast: ToastState): AppShellAction => ({
  type: "showToast",
  toast,
});

export const clearToast = (): AppShellAction => ({
  type: "clearToast",
});
