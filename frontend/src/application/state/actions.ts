import type { WorkflowParams } from "../../domain/ree/ReeTypes";
import type {
  AppShellAction,
  PatchAction,
  SliceName,
  SliceShape,
  SourceOutcomePayload,
  WorkflowRunCompletionPayload,
} from "../app-shell/AppShellTypes";
import type { Updater } from "./types";

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

export const completeWorkflowRun = (completion: WorkflowRunCompletionPayload): AppShellAction => ({
  type: "completeWorkflowRun",
  completion,
});

export const resetWorkflowOnSourceChange = (workflowParams: WorkflowParams): AppShellAction => ({
  type: "resetWorkflowOnSourceChange",
  workflowParams,
});
