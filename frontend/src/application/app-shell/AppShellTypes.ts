import type { ArtifactStatus } from "../../domain/artifact/ArtifactStatus";
import type { ReeSpec } from "../../domain/ree/ReeSpec";
import type { ActionStates, Badges, Timestamps, WorkflowParams } from "../../domain/ree/ReeTypes";
import type { EvaluationState } from "../../domain/review/EvaluationState";
import type { WorkspaceSourceState } from "../../domain/workspace/WorkspaceSourceState";
import type { ReeDraftState, ReeDraftStateUpdater } from "../ree-draft/ReeDraftState";
import type { UiChromeState, UiChromeStateUpdater } from "../ui-chrome/UiChromeState";
import type { ToastState } from "../workflow/WorkflowStepTypes";
import type { WorkflowRunState, WorkflowRunStateUpdater } from "../workflow-runs/WorkflowRunState";
import type { AppShellPage } from "./AppShellPages";
import type {
  AppShellState,
  SourceOutcomePayload,
  WorkflowRunCompletionPayload,
} from "./AppShellState";

export type StateUpdater<T> = ReeDraftStateUpdater<T>;

export interface AppShellContextState {
  reeDraft: ReeDraftState;
  workflowRun: WorkflowRunState;
  uiChrome: UiChromeState;
}

export type AppShellAction =
  | { type: "appShell/setReeSpec"; reeSpec: ReeDraftStateUpdater<ReeSpec> }
  | { type: "appShell/setLocked"; locked: ReeDraftStateUpdater<boolean> }
  | {
      type: "appShell/setRepoMode";
      repoMode: ReeDraftStateUpdater<"url" | "upload">;
    }
  | {
      type: "appShell/setWorkspaceSourceState";
      workspaceSourceState: ReeDraftStateUpdater<WorkspaceSourceState>;
    }
  | {
      type: "appShell/setArtifactStatus";
      artifactStatus: ReeDraftStateUpdater<ArtifactStatus>;
    }
  | {
      type: "appShell/setActionStates";
      actionStates: WorkflowRunStateUpdater<ActionStates>;
    }
  | { type: "appShell/setBadges"; badges: WorkflowRunStateUpdater<Badges> }
  | { type: "appShell/setTimestamps"; timestamps: WorkflowRunStateUpdater<Timestamps> }
  | {
      type: "appShell/setWorkflowParams";
      workflowParams: WorkflowRunStateUpdater<WorkflowParams>;
    }
  | {
      type: "appShell/setEvaluationState";
      evaluationState: WorkflowRunStateUpdater<EvaluationState>;
    }
  | { type: "appShell/setActiveRunId"; payload: { key: string; runId: string } }
  | { type: "appShell/setToast"; toast: UiChromeStateUpdater<ToastState | null> }
  | {
      type: "appShell/setPage";
      page: UiChromeStateUpdater<AppShellPage>;
    }
  | {
      type: "appShell/setFocusedField";
      focusedField: UiChromeStateUpdater<string | null>;
    }
  | {
      type: "appShell/setNavCollapsed";
      navCollapsed: UiChromeStateUpdater<boolean>;
    }
  | {
      type: "appShell/setSourceSnapshotArchiveName";
      sourceSnapshotArchiveName: ReeDraftStateUpdater<string>;
    }
  | { type: "appShell/applySourceOutcome"; outcome: SourceOutcomePayload }
  | {
      type: "appShell/setShowReviewPreview";
      showReviewPreview: UiChromeStateUpdater<boolean>;
    }
  | { type: "appShell/completeWorkflowRun"; completion: WorkflowRunCompletionPayload }
  | { type: "appShell/resetWorkflowOnSourceChange"; workflowParams: WorkflowParams };

export type { AppShellState, SourceOutcomePayload, WorkflowRunCompletionPayload };
