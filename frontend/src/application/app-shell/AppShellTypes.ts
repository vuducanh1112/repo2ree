import type { WorkflowParams } from "../../domain/ree/ReeTypes";
import type { ReeDraftState } from "../ree-draft/ReeDraftState";
import type { Updater } from "../state/types";
import type { UiChromeState } from "../ui-chrome/UiChromeState";
import type { WorkflowRunState } from "../workflow-runs/WorkflowRunState";
import type { SourceOutcomePayload, WorkflowRunCompletionPayload } from "./AppShellState";

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
