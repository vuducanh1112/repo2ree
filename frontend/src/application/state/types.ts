import type { ArtifactStatus } from "../../core/artifact/ArtifactStatus";
import type { ReeSpec } from "../../core/ree/ReeSpec";
import type { ReeAssemblyOperationParams } from "../../core/ree/ReeTypes";
import type { EvaluationState } from "../../core/review/EvaluationState";
import type { WorkspaceSourceState } from "../../core/workspace/WorkspaceSourceState";
import type { ToastState } from "../ree-assembly/assemblyStepTypes";
import type { AssemblyRunCompletionPayload, SourceOutcomePayload } from "./appShellState";
import type { AssemblyRunState } from "./assemblyRunState";
import type { ReeDraftState } from "./reeDraft";
import type { UiChromeState } from "./uiChrome";

export type Updater<T> = T | ((previous: T) => T);

export function resolveUpdater<T>(previous: T, updater: Updater<T>): T {
  return typeof updater === "function" ? (updater as (value: T) => T)(previous) : updater;
}

export interface SliceShape {
  reeDraft: ReeDraftState;
  assemblyRun: AssemblyRunState;
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
  | { type: "setAssemblyOperationParams"; value: Updater<ReeAssemblyOperationParams> }
  | { type: "setActiveRunId"; key: string; runId: string }
  | { type: "setLocked"; locked: boolean }
  | { type: "setRepoMode"; repoMode: "url" | "upload" }
  | { type: "setAssemblyRunLoading"; key: string }
  | { type: "completeAssemblyRun"; completion: AssemblyRunCompletionPayload }
  | { type: "resetAssemblyAfterSourceChange"; assemblyOperationParams: ReeAssemblyOperationParams }
  | { type: "showToast"; toast: ToastState }
  | { type: "clearToast" }
  | { type: "applySourceOutcome"; outcome: SourceOutcomePayload };

export type { AssemblyRunCompletionPayload, SourceOutcomePayload };
