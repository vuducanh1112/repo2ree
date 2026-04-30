import { enforceSourceOriginRules } from "../../domain/artifact/sourceOriginRules";
import type { Ree } from "../../domain/ree/ReeSpec";
import type {
  ActionStates,
  Badges,
  ReeFile,
  Timestamps,
  WorkflowLogs,
  WorkflowParams,
} from "../../domain/ree/ReeTypes";
import type { FileTreeNode } from "../../domain/workspace/FileTree";
import { computeSourceChangeConsequences } from "../../domain/workspace/sourceChangeConsequences";
import { initialAutomationStepParams } from "../workflow/WorkflowStepDefinitions";
import type { ToastState } from "../workflow/WorkflowStepTypes";
import { normalizeWorkspaceEditorPage } from "./WorkspaceEditorNavigation";
import type { WorkspaceEditorPage } from "./WorkspaceEditorPages";
import { PAGE } from "./WorkspaceEditorPages";

export type WorkspaceEditorStateUpdater<T> = T | ((previous: T) => T);

export interface WorkspaceEditorState {
  ree: Ree;
  locked: boolean;
  repoMode: "url" | "upload";
  actionStates: ActionStates;
  badges: Badges;
  timestamps: Timestamps;
  workflowLogs: WorkflowLogs;
  workflowParams: WorkflowParams;
  toast: ToastState | null;
  page: WorkspaceEditorPage;
  focusedField: string | null;
  navCollapsed: boolean;
  workspaceFiles: FileTreeNode[];
  reeArtifactFiles: ReeFile[];
  sourceSnapshotFiles: FileTreeNode[];
  sourceSnapshotArchiveName: string;
  showReviewPreview: boolean;
}

export interface WorkspaceHydrationPayload {
  workspaceFiles: FileTreeNode[];
  reeArtifactFiles: ReeFile[];
  ree?: Ree;
}

export interface SourceOutcomePayload {
  reePatch: Partial<Ree>;
  sourceSnapshotFiles: FileTreeNode[];
  sourceSnapshotArchiveName: string;
  actionState?: "done";
  badge?: boolean;
  timestamp?: string;
}

export interface WorkflowRunCompletionPayload {
  key: string;
  workflowLog: WorkflowLogs[string];
  actionState: "done";
  badge: boolean;
  timestamp: string;
}

export type WorkspaceEditorAction =
  | { type: "workspaceEditor/setRee"; ree: WorkspaceEditorStateUpdater<Ree> }
  | { type: "workspaceEditor/setLocked"; locked: WorkspaceEditorStateUpdater<boolean> }
  | {
      type: "workspaceEditor/setRepoMode";
      repoMode: WorkspaceEditorStateUpdater<"url" | "upload">;
    }
  | {
      type: "workspaceEditor/setActionStates";
      actionStates: WorkspaceEditorStateUpdater<ActionStates>;
    }
  | { type: "workspaceEditor/setBadges"; badges: WorkspaceEditorStateUpdater<Badges> }
  | { type: "workspaceEditor/setTimestamps"; timestamps: WorkspaceEditorStateUpdater<Timestamps> }
  | {
      type: "workspaceEditor/setWorkflowLogs";
      workflowLogs: WorkspaceEditorStateUpdater<WorkflowLogs>;
    }
  | {
      type: "workspaceEditor/setWorkflowParams";
      workflowParams: WorkspaceEditorStateUpdater<WorkflowParams>;
    }
  | { type: "workspaceEditor/setToast"; toast: WorkspaceEditorStateUpdater<ToastState | null> }
  | {
      type: "workspaceEditor/setPage";
      page: WorkspaceEditorStateUpdater<WorkspaceEditorPage>;
    }
  | {
      type: "workspaceEditor/setFocusedField";
      focusedField: WorkspaceEditorStateUpdater<string | null>;
    }
  | {
      type: "workspaceEditor/setNavCollapsed";
      navCollapsed: WorkspaceEditorStateUpdater<boolean>;
    }
  | {
      type: "workspaceEditor/setWorkspaceFiles";
      workspaceFiles: WorkspaceEditorStateUpdater<FileTreeNode[]>;
    }
  | {
      type: "workspaceEditor/setReeArtifactFiles";
      reeArtifactFiles: WorkspaceEditorStateUpdater<ReeFile[]>;
    }
  | { type: "workspaceEditor/hydrateWorkspace"; workspace: WorkspaceHydrationPayload }
  | {
      type: "workspaceEditor/setSourceSnapshotFiles";
      sourceSnapshotFiles: WorkspaceEditorStateUpdater<FileTreeNode[]>;
    }
  | {
      type: "workspaceEditor/setSourceSnapshotArchiveName";
      sourceSnapshotArchiveName: WorkspaceEditorStateUpdater<string>;
    }
  | { type: "workspaceEditor/applySourcePatchOutcome"; outcome: SourceOutcomePayload }
  | {
      type: "workspaceEditor/setShowReviewPreview";
      showReviewPreview: WorkspaceEditorStateUpdater<boolean>;
    }
  | { type: "workspaceEditor/completeWorkflowRun"; completion: WorkflowRunCompletionPayload }
  | { type: "workspaceEditor/resetWorkflowOnSourceChange"; workflowParams: WorkflowParams };

function resolveUpdater<T>(previous: T, updater: WorkspaceEditorStateUpdater<T>): T {
  if (typeof updater === "function") {
    return (updater as (value: T) => T)(previous);
  }
  return updater;
}

export function createInitialWorkspaceEditorState(
  initialWorkspaceEditorRee: Ree,
): WorkspaceEditorState {
  return {
    ree: enforceSourceOriginRules(initialWorkspaceEditorRee),
    locked: false,
    repoMode: "url",
    actionStates: {},
    badges: {},
    timestamps: {},
    workflowLogs: {},
    workflowParams: initialAutomationStepParams(),
    toast: null,
    page: PAGE.SOURCE,
    focusedField: null,
    navCollapsed: false,
    workspaceFiles: [],
    reeArtifactFiles: [],
    sourceSnapshotFiles: [],
    sourceSnapshotArchiveName: "",
    showReviewPreview: false,
  };
}

export function applyWorkspaceEditorAction(
  state: WorkspaceEditorState,
  action: WorkspaceEditorAction,
): WorkspaceEditorState {
  switch (action.type) {
    case "workspaceEditor/setRee": {
      const nextRee = enforceSourceOriginRules(resolveUpdater(state.ree, action.ree));
      return { ...state, ree: nextRee };
    }
    case "workspaceEditor/setLocked": {
      return { ...state, locked: resolveUpdater(state.locked, action.locked) };
    }
    case "workspaceEditor/setRepoMode": {
      return { ...state, repoMode: resolveUpdater(state.repoMode, action.repoMode) };
    }
    case "workspaceEditor/setActionStates": {
      return { ...state, actionStates: resolveUpdater(state.actionStates, action.actionStates) };
    }
    case "workspaceEditor/setBadges": {
      return { ...state, badges: resolveUpdater(state.badges, action.badges) };
    }
    case "workspaceEditor/setTimestamps": {
      return { ...state, timestamps: resolveUpdater(state.timestamps, action.timestamps) };
    }
    case "workspaceEditor/setWorkflowLogs": {
      return { ...state, workflowLogs: resolveUpdater(state.workflowLogs, action.workflowLogs) };
    }
    case "workspaceEditor/setWorkflowParams": {
      return {
        ...state,
        workflowParams: resolveUpdater(state.workflowParams, action.workflowParams),
      };
    }
    case "workspaceEditor/setToast": {
      return { ...state, toast: resolveUpdater(state.toast, action.toast) };
    }
    case "workspaceEditor/setPage": {
      const candidate = resolveUpdater(state.page, action.page);
      return { ...state, page: normalizeWorkspaceEditorPage(candidate, state.page) };
    }
    case "workspaceEditor/setFocusedField": {
      return { ...state, focusedField: resolveUpdater(state.focusedField, action.focusedField) };
    }
    case "workspaceEditor/setNavCollapsed": {
      return { ...state, navCollapsed: resolveUpdater(state.navCollapsed, action.navCollapsed) };
    }
    case "workspaceEditor/setWorkspaceFiles": {
      return {
        ...state,
        workspaceFiles: resolveUpdater(state.workspaceFiles, action.workspaceFiles),
      };
    }
    case "workspaceEditor/setReeArtifactFiles": {
      return {
        ...state,
        reeArtifactFiles: resolveUpdater(state.reeArtifactFiles, action.reeArtifactFiles),
      };
    }
    case "workspaceEditor/hydrateWorkspace": {
      return {
        ...state,
        workspaceFiles: action.workspace.workspaceFiles,
        reeArtifactFiles: action.workspace.reeArtifactFiles,
        ree: action.workspace.ree ? enforceSourceOriginRules(action.workspace.ree) : state.ree,
      };
    }
    case "workspaceEditor/setSourceSnapshotFiles": {
      return {
        ...state,
        sourceSnapshotFiles: resolveUpdater(state.sourceSnapshotFiles, action.sourceSnapshotFiles),
      };
    }
    case "workspaceEditor/setSourceSnapshotArchiveName": {
      return {
        ...state,
        sourceSnapshotArchiveName: resolveUpdater(
          state.sourceSnapshotArchiveName,
          action.sourceSnapshotArchiveName,
        ),
      };
    }
    case "workspaceEditor/applySourcePatchOutcome": {
      const nextRee = enforceSourceOriginRules({
        ...state.ree,
        ...action.outcome.reePatch,
      });
      return {
        ...state,
        ree: nextRee,
        sourceSnapshotFiles: action.outcome.sourceSnapshotFiles,
        sourceSnapshotArchiveName: action.outcome.sourceSnapshotArchiveName,
        actionStates: action.outcome.actionState
          ? { ...state.actionStates, source: action.outcome.actionState }
          : state.actionStates,
        badges:
          typeof action.outcome.badge === "boolean"
            ? { ...state.badges, source: action.outcome.badge }
            : state.badges,
        timestamps: action.outcome.timestamp
          ? { ...state.timestamps, source: action.outcome.timestamp }
          : state.timestamps,
      };
    }
    case "workspaceEditor/setShowReviewPreview": {
      return {
        ...state,
        showReviewPreview: resolveUpdater(state.showReviewPreview, action.showReviewPreview),
      };
    }
    case "workspaceEditor/completeWorkflowRun": {
      return {
        ...state,
        workflowLogs: {
          ...state.workflowLogs,
          [action.completion.key]: action.completion.workflowLog,
        },
        actionStates: {
          ...state.actionStates,
          [action.completion.key]: action.completion.actionState,
        },
        badges: {
          ...state.badges,
          [action.completion.key]: action.completion.badge,
        },
        timestamps: {
          ...state.timestamps,
          [action.completion.key]: action.completion.timestamp,
        },
      };
    }
    case "workspaceEditor/resetWorkflowOnSourceChange": {
      return {
        ...state,
        ...computeSourceChangeConsequences(state, action.workflowParams),
      };
    }
    default:
      return state;
  }
}
