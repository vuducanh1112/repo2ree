import { PAGE } from "../../constants/pages";
import { initialAutomationStepParams } from "../../constants/workflowSteps";
import { enforceSourceOriginRules } from "../../domain/artifact/sourceOriginRules";
import { computeSourceChangeConsequences } from "../../domain/workspace/sourceChangeConsequences";
import type {
  ActionStates,
  Badges,
  FileTreeNode,
  Ree,
  ReeFile,
  ServiceLogs,
  ServiceParams,
  Timestamps,
  ToastState,
  WorkspaceEditorPage,
} from "../../types";
import { normalizeWorkspaceEditorPage } from "./workspaceEditorNavigation";

export type WorkspaceEditorStateUpdater<T> = T | ((previous: T) => T);

export interface WorkspaceEditorState {
  ree: Ree;
  locked: boolean;
  repoMode: "url" | "upload";
  actionStates: ActionStates;
  badges: Badges;
  timestamps: Timestamps;
  serviceLogs: ServiceLogs;
  serviceParams: ServiceParams;
  toast: ToastState | null;
  page: WorkspaceEditorPage;
  focusedField: string | null;
  navCollapsed: boolean;
  virtualFiles: FileTreeNode[];
  workspaceReeFiles: ReeFile[];
  immutableSourceSnapshotFiles: FileTreeNode[];
  immutableSourceSnapshotArchiveName: string;
  showReviewerPreview: boolean;
}

export interface WorkspaceHydrationPayload {
  virtualFiles: FileTreeNode[];
  workspaceReeFiles: ReeFile[];
  ree?: Ree;
}

export interface SourceOutcomePayload {
  reePatch: Partial<Ree>;
  immutableSourceSnapshotFiles: FileTreeNode[];
  immutableSourceSnapshotArchiveName: string;
  actionState?: "done";
  badge?: boolean;
  timestamp?: string;
}

export interface WorkflowRunCompletionPayload {
  key: string;
  serviceLog: ServiceLogs[string];
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
      type: "workspaceEditor/setServiceLogs";
      serviceLogs: WorkspaceEditorStateUpdater<ServiceLogs>;
    }
  | {
      type: "workspaceEditor/setServiceParams";
      serviceParams: WorkspaceEditorStateUpdater<ServiceParams>;
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
      type: "workspaceEditor/setVirtualFiles";
      virtualFiles: WorkspaceEditorStateUpdater<FileTreeNode[]>;
    }
  | {
      type: "workspaceEditor/setWorkspaceReeFiles";
      workspaceReeFiles: WorkspaceEditorStateUpdater<ReeFile[]>;
    }
  | { type: "workspaceEditor/hydrateWorkspace"; workspace: WorkspaceHydrationPayload }
  | {
      type: "workspaceEditor/setImmutableSourceSnapshotFiles";
      immutableSourceSnapshotFiles: WorkspaceEditorStateUpdater<FileTreeNode[]>;
    }
  | {
      type: "workspaceEditor/setImmutableSourceSnapshotArchiveName";
      immutableSourceSnapshotArchiveName: WorkspaceEditorStateUpdater<string>;
    }
  | { type: "workspaceEditor/applySourcePatchOutcome"; outcome: SourceOutcomePayload }
  | {
      type: "workspaceEditor/setShowReviewerPreview";
      showReviewerPreview: WorkspaceEditorStateUpdater<boolean>;
    }
  | { type: "workspaceEditor/completeWorkflowRun"; completion: WorkflowRunCompletionPayload }
  | { type: "workspaceEditor/resetWorkflowOnSourceChange"; serviceParams: ServiceParams };

function resolveUpdater<T>(previous: T, updater: WorkspaceEditorStateUpdater<T>): T {
  if (typeof updater === "function") {
    return (updater as (value: T) => T)(previous);
  }
  return updater;
}

export function createInitialWorkspaceEditorState(initialExplorerRee: Ree): WorkspaceEditorState {
  return {
    ree: enforceSourceOriginRules(initialExplorerRee),
    locked: false,
    repoMode: "url",
    actionStates: {},
    badges: {},
    timestamps: {},
    serviceLogs: {},
    serviceParams: initialAutomationStepParams(),
    toast: null,
    page: PAGE.SOURCE,
    focusedField: null,
    navCollapsed: false,
    virtualFiles: [],
    workspaceReeFiles: [],
    immutableSourceSnapshotFiles: [],
    immutableSourceSnapshotArchiveName: "",
    showReviewerPreview: false,
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
    case "workspaceEditor/setServiceLogs": {
      return { ...state, serviceLogs: resolveUpdater(state.serviceLogs, action.serviceLogs) };
    }
    case "workspaceEditor/setServiceParams": {
      return { ...state, serviceParams: resolveUpdater(state.serviceParams, action.serviceParams) };
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
    case "workspaceEditor/setVirtualFiles": {
      return { ...state, virtualFiles: resolveUpdater(state.virtualFiles, action.virtualFiles) };
    }
    case "workspaceEditor/setWorkspaceReeFiles": {
      return {
        ...state,
        workspaceReeFiles: resolveUpdater(state.workspaceReeFiles, action.workspaceReeFiles),
      };
    }
    case "workspaceEditor/hydrateWorkspace": {
      return {
        ...state,
        virtualFiles: action.workspace.virtualFiles,
        workspaceReeFiles: action.workspace.workspaceReeFiles,
        ree: action.workspace.ree ? enforceSourceOriginRules(action.workspace.ree) : state.ree,
      };
    }
    case "workspaceEditor/setImmutableSourceSnapshotFiles": {
      return {
        ...state,
        immutableSourceSnapshotFiles: resolveUpdater(
          state.immutableSourceSnapshotFiles,
          action.immutableSourceSnapshotFiles,
        ),
      };
    }
    case "workspaceEditor/setImmutableSourceSnapshotArchiveName": {
      return {
        ...state,
        immutableSourceSnapshotArchiveName: resolveUpdater(
          state.immutableSourceSnapshotArchiveName,
          action.immutableSourceSnapshotArchiveName,
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
        immutableSourceSnapshotFiles: action.outcome.immutableSourceSnapshotFiles,
        immutableSourceSnapshotArchiveName: action.outcome.immutableSourceSnapshotArchiveName,
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
    case "workspaceEditor/setShowReviewerPreview": {
      return {
        ...state,
        showReviewerPreview: resolveUpdater(state.showReviewerPreview, action.showReviewerPreview),
      };
    }
    case "workspaceEditor/completeWorkflowRun": {
      return {
        ...state,
        serviceLogs: {
          ...state.serviceLogs,
          [action.completion.key]: action.completion.serviceLog,
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
        ...computeSourceChangeConsequences(state, action.serviceParams),
      };
    }
    default:
      return state;
  }
}
