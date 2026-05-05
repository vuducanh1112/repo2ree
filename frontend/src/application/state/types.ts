import type { WorkflowParams } from "../../domain/ree/ReeTypes";
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
  | { type: "applySourceOutcome"; outcome: SourceOutcomePayload }
  | { type: "completeWorkflowRun"; completion: WorkflowRunCompletionPayload }
  | { type: "resetWorkflowOnSourceChange"; workflowParams: WorkflowParams };

export type { SourceOutcomePayload, WorkflowRunCompletionPayload };
