import type { ArtifactStatus } from "../../domain/artifact/ArtifactStatus";
import type { ReeSpec } from "../../domain/ree/ReeSpec";
import type { WorkflowParams } from "../../domain/ree/ReeTypes";
import type { EvaluationState } from "../../domain/review/EvaluationState";
import type { WorkspaceSourceState } from "../../domain/workspace/WorkspaceSourceState";
import type { ToastState } from "../workflow/WorkflowStepTypes";
import type { SourceOutcomePayload, WorkflowRunCompletionPayload } from "./appShellState";
import type { ReeDraftState } from "./reeDraft";
import type { UiChromeState } from "./uiChrome";
import type { WorkflowRunState } from "./workflowRun";

export type Updater<T> = T | ((previous: T) => T);

export function resolveUpdater<T>(previous: T, updater: Updater<T>): T {
  return typeof updater === "function" ? (updater as (value: T) => T)(previous) : updater;
}

export interface SliceShape {
  reeDraft: ReeDraftState;
  workflowRun: WorkflowRunState;
  uiChrome: UiChromeState;
}

export type SliceName = keyof SliceShape;

export interface AppShellContextState extends SliceShape {}

export type PatchAction = {
  [Slice in SliceName]: {
    type: "patch";
    slice: Slice;
    updater: Updater<Partial<SliceShape[Slice]>>;
  };
}[SliceName];

export type AppShellAction =
  | PatchAction
  | { type: "updateReeSpec"; value: Updater<ReeSpec> }
  | { type: "setWorkspaceSourceState"; value: Updater<WorkspaceSourceState> }
  | { type: "setArtifactStatus"; value: Updater<ArtifactStatus> }
  | { type: "setEvaluationState"; value: Updater<EvaluationState> }
  | { type: "setWorkflowParams"; value: Updater<WorkflowParams> }
  | { type: "setActiveRunId"; key: string; runId: string }
  | { type: "setLocked"; locked: boolean }
  | { type: "setAssemblyRunLoading"; key: string }
  | { type: "completeAssemblyRun"; completion: WorkflowRunCompletionPayload }
  | { type: "resetAssemblyAfterSourceChange"; workflowParams: WorkflowParams }
  | { type: "showToast"; toast: ToastState }
  | { type: "clearToast" }
  | { type: "applySourceOutcome"; outcome: SourceOutcomePayload }
  | { type: "completeWorkflowRun"; completion: WorkflowRunCompletionPayload }
  | { type: "resetWorkflowOnSourceChange"; workflowParams: WorkflowParams };

export type { SourceOutcomePayload, WorkflowRunCompletionPayload };
