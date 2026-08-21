import type { ArtifactStatus } from "@core/artifact/ArtifactStatus";
import type { EvaluationState } from "@core/evaluate/EvaluationState";
import type { ReeSpec } from "@core/ree/ReeSpec";
import type { ReeStepParams } from "@core/ree/ReeTypes";
import type { ToastState } from "@core/ree-steps/stepTypes";
import type { WorkspaceSourceState } from "@core/workspace/WorkspaceSourceState";
import type { SourceOutcomePayload, StepRunCompletionPayload } from "./appShellState";
import type { ReeIntentState } from "./reeIntent";
import type { ReeSessionState } from "./reeSession";
import type { StepRunState } from "./stepRunState";
import type { UiChromeState } from "./uiChrome";

export type Updater<T> = T | ((previous: T) => T);

export function resolveUpdater<T>(previous: T, updater: Updater<T>): T {
  return typeof updater === "function" ? (updater as (value: T) => T)(previous) : updater;
}

export interface SliceShape {
  reeIntent: ReeIntentState;
  reeSession: ReeSessionState;
  stepRuns: StepRunState;
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
  | { type: "setStepParams"; value: Updater<ReeStepParams> }
  | { type: "setActiveRunId"; key: string; runId: string }
  | { type: "cancelStepRun"; key: string; runId?: string }
  | { type: "setLocked"; value: Updater<boolean> }
  | { type: "setRepoMode"; value: Updater<"url" | "upload"> }
  | { type: "setFocusedField"; value: Updater<string | null> }
  | { type: "setStepRunLoading"; key: string }
  | { type: "completeStepRun"; completion: StepRunCompletionPayload }
  | { type: "resetStepsAfterSourceChange"; stepParams: ReeStepParams }
  | { type: "showToast"; toast: ToastState }
  | { type: "clearToast" }
  | { type: "applySourceOutcome"; outcome: SourceOutcomePayload };

export type { SourceOutcomePayload, StepRunCompletionPayload };
