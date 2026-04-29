import { PAGE } from "../../constants/pages";
import { initialServiceParams } from "../../constants/services";
import { enforceSourceOriginContract } from "../../domain/ree/sourceContract";
import { computeExplorerSourceChangeReset } from "../../domain/workflow/sourceChangeReset";
import type {
  ActionStates,
  Badges,
  ExplorerPage,
  FileTreeNode,
  Ree,
  ReeFile,
  ServiceLogs,
  ServiceParams,
  Timestamps,
  ToastState,
} from "../../types";
import { normalizeExplorerPage } from "./navigation";

export type ExplorerStateUpdater<T> = T | ((previous: T) => T);

export interface ExplorerState {
  ree: Ree;
  locked: boolean;
  repoMode: "url" | "upload";
  actionStates: ActionStates;
  badges: Badges;
  timestamps: Timestamps;
  serviceLogs: ServiceLogs;
  serviceParams: ServiceParams;
  toast: ToastState | null;
  page: ExplorerPage;
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

export interface ServiceRunCompletionPayload {
  key: string;
  serviceLog: ServiceLogs[string];
  actionState: "done";
  badge: boolean;
  timestamp: string;
}

export type ExplorerAction =
  | { type: "explorer/setRee"; ree: ExplorerStateUpdater<Ree> }
  | { type: "explorer/setLocked"; locked: ExplorerStateUpdater<boolean> }
  | { type: "explorer/setRepoMode"; repoMode: ExplorerStateUpdater<"url" | "upload"> }
  | { type: "explorer/setActionStates"; actionStates: ExplorerStateUpdater<ActionStates> }
  | { type: "explorer/setBadges"; badges: ExplorerStateUpdater<Badges> }
  | { type: "explorer/setTimestamps"; timestamps: ExplorerStateUpdater<Timestamps> }
  | { type: "explorer/setServiceLogs"; serviceLogs: ExplorerStateUpdater<ServiceLogs> }
  | { type: "explorer/setServiceParams"; serviceParams: ExplorerStateUpdater<ServiceParams> }
  | { type: "explorer/setToast"; toast: ExplorerStateUpdater<ToastState | null> }
  | { type: "explorer/setPage"; page: ExplorerStateUpdater<ExplorerPage> }
  | { type: "explorer/setFocusedField"; focusedField: ExplorerStateUpdater<string | null> }
  | { type: "explorer/setNavCollapsed"; navCollapsed: ExplorerStateUpdater<boolean> }
  | { type: "explorer/setVirtualFiles"; virtualFiles: ExplorerStateUpdater<FileTreeNode[]> }
  | { type: "explorer/setWorkspaceReeFiles"; workspaceReeFiles: ExplorerStateUpdater<ReeFile[]> }
  | { type: "explorer/hydrateWorkspace"; workspace: WorkspaceHydrationPayload }
  | {
      type: "explorer/setImmutableSourceSnapshotFiles";
      immutableSourceSnapshotFiles: ExplorerStateUpdater<FileTreeNode[]>;
    }
  | {
      type: "explorer/setImmutableSourceSnapshotArchiveName";
      immutableSourceSnapshotArchiveName: ExplorerStateUpdater<string>;
    }
  | { type: "explorer/applySourcePatchOutcome"; outcome: SourceOutcomePayload }
  | {
      type: "explorer/setShowReviewerPreview";
      showReviewerPreview: ExplorerStateUpdater<boolean>;
    }
  | { type: "explorer/completeServiceRun"; completion: ServiceRunCompletionPayload }
  | { type: "explorer/resetWorkflowOnSourceChange"; serviceParams: ServiceParams };

function resolveUpdater<T>(previous: T, updater: ExplorerStateUpdater<T>): T {
  if (typeof updater === "function") {
    return (updater as (value: T) => T)(previous);
  }
  return updater;
}

export function createInitialExplorerState(initialExplorerRee: Ree): ExplorerState {
  return {
    ree: enforceSourceOriginContract(initialExplorerRee),
    locked: false,
    repoMode: "url",
    actionStates: {},
    badges: {},
    timestamps: {},
    serviceLogs: {},
    serviceParams: initialServiceParams(),
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

export function applyExplorerAction(state: ExplorerState, action: ExplorerAction): ExplorerState {
  switch (action.type) {
    case "explorer/setRee": {
      const nextRee = enforceSourceOriginContract(resolveUpdater(state.ree, action.ree));
      return { ...state, ree: nextRee };
    }
    case "explorer/setLocked": {
      return { ...state, locked: resolveUpdater(state.locked, action.locked) };
    }
    case "explorer/setRepoMode": {
      return { ...state, repoMode: resolveUpdater(state.repoMode, action.repoMode) };
    }
    case "explorer/setActionStates": {
      return { ...state, actionStates: resolveUpdater(state.actionStates, action.actionStates) };
    }
    case "explorer/setBadges": {
      return { ...state, badges: resolveUpdater(state.badges, action.badges) };
    }
    case "explorer/setTimestamps": {
      return { ...state, timestamps: resolveUpdater(state.timestamps, action.timestamps) };
    }
    case "explorer/setServiceLogs": {
      return { ...state, serviceLogs: resolveUpdater(state.serviceLogs, action.serviceLogs) };
    }
    case "explorer/setServiceParams": {
      return { ...state, serviceParams: resolveUpdater(state.serviceParams, action.serviceParams) };
    }
    case "explorer/setToast": {
      return { ...state, toast: resolveUpdater(state.toast, action.toast) };
    }
    case "explorer/setPage": {
      const candidate = resolveUpdater(state.page, action.page);
      return { ...state, page: normalizeExplorerPage(candidate, state.page) };
    }
    case "explorer/setFocusedField": {
      return { ...state, focusedField: resolveUpdater(state.focusedField, action.focusedField) };
    }
    case "explorer/setNavCollapsed": {
      return { ...state, navCollapsed: resolveUpdater(state.navCollapsed, action.navCollapsed) };
    }
    case "explorer/setVirtualFiles": {
      return { ...state, virtualFiles: resolveUpdater(state.virtualFiles, action.virtualFiles) };
    }
    case "explorer/setWorkspaceReeFiles": {
      return {
        ...state,
        workspaceReeFiles: resolveUpdater(state.workspaceReeFiles, action.workspaceReeFiles),
      };
    }
    case "explorer/hydrateWorkspace": {
      return {
        ...state,
        virtualFiles: action.workspace.virtualFiles,
        workspaceReeFiles: action.workspace.workspaceReeFiles,
        ree: action.workspace.ree ? enforceSourceOriginContract(action.workspace.ree) : state.ree,
      };
    }
    case "explorer/setImmutableSourceSnapshotFiles": {
      return {
        ...state,
        immutableSourceSnapshotFiles: resolveUpdater(
          state.immutableSourceSnapshotFiles,
          action.immutableSourceSnapshotFiles,
        ),
      };
    }
    case "explorer/setImmutableSourceSnapshotArchiveName": {
      return {
        ...state,
        immutableSourceSnapshotArchiveName: resolveUpdater(
          state.immutableSourceSnapshotArchiveName,
          action.immutableSourceSnapshotArchiveName,
        ),
      };
    }
    case "explorer/applySourcePatchOutcome": {
      const nextRee = enforceSourceOriginContract({
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
    case "explorer/setShowReviewerPreview": {
      return {
        ...state,
        showReviewerPreview: resolveUpdater(state.showReviewerPreview, action.showReviewerPreview),
      };
    }
    case "explorer/completeServiceRun": {
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
    case "explorer/resetWorkflowOnSourceChange": {
      return {
        ...state,
        ...computeExplorerSourceChangeReset(state, action.serviceParams),
      };
    }
    default:
      return state;
  }
}
