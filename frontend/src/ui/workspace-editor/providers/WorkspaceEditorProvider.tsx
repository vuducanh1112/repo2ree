import type { ReactNode } from "react";
import { createContext, useContext, useMemo, useReducer } from "react";
import {
  createInitialUiChromeState,
  resolveUiChromeUpdater,
} from "../../../application/ui-chrome/UiChromeState";
import {
  createInitialWorkflowRunState,
  resolveWorkflowRunUpdater,
} from "../../../application/workflow-runs/WorkflowRunState";
import {
  createInitialWorkspaceDraftState,
  resolveWorkspaceDraftUpdater,
} from "../../../application/workspace-draft/WorkspaceDraftState";
import { normalizeUiChromePage } from "../../../application/workspace-editor/WorkspaceEditorState";
import type {
  WorkspaceEditorAction,
  WorkspaceEditorContextState,
} from "../../../application/workspace-editor/WorkspaceEditorTypes";
import {
  createInitialWorkspaceRemoteState,
  resolveWorkspaceRemoteUpdater,
} from "../../../application/workspace-remote/WorkspaceRemoteState";
import { enforceSourceOriginRules } from "../../../domain/artifact/sourceOriginRules";
import type { Ree } from "../../../domain/ree/ReeSpec";
import { computeSourceChangeConsequences } from "../../../domain/workspace/sourceChangeConsequences";

interface WorkspaceEditorContextValue {
  state: WorkspaceEditorContextState;
  dispatch: React.Dispatch<WorkspaceEditorAction>;
}

const WorkspaceEditorContext = createContext<WorkspaceEditorContextValue | null>(null);

interface WorkspaceEditorProviderProps {
  children: ReactNode;
  initialWorkspaceEditorRee: Ree;
}

export function createInitialState(initialWorkspaceEditorRee: Ree): WorkspaceEditorContextState {
  return {
    workspaceDraft: createInitialWorkspaceDraftState(initialWorkspaceEditorRee),
    workspaceRemote: createInitialWorkspaceRemoteState(),
    workflowRun: createInitialWorkflowRunState(),
    uiChrome: createInitialUiChromeState(),
  };
}

export function workspaceEditorReducer(
  state: WorkspaceEditorContextState,
  action: WorkspaceEditorAction,
): WorkspaceEditorContextState {
  switch (action.type) {
    case "workspaceEditor/setRee":
      return {
        ...state,
        workspaceDraft: {
          ...state.workspaceDraft,
          ree: enforceSourceOriginRules(
            resolveWorkspaceDraftUpdater(state.workspaceDraft.ree, action.ree),
          ),
        },
      };
    case "workspaceEditor/setLocked":
      return {
        ...state,
        workspaceDraft: {
          ...state.workspaceDraft,
          locked: resolveWorkspaceDraftUpdater(state.workspaceDraft.locked, action.locked),
        },
      };
    case "workspaceEditor/setRepoMode":
      return {
        ...state,
        workspaceDraft: {
          ...state.workspaceDraft,
          repoMode: resolveWorkspaceDraftUpdater(state.workspaceDraft.repoMode, action.repoMode),
        },
      };
    case "workspaceEditor/setActionStates":
      return {
        ...state,
        workflowRun: {
          ...state.workflowRun,
          actionStates: resolveWorkflowRunUpdater(
            state.workflowRun.actionStates,
            action.actionStates,
          ),
        },
      };
    case "workspaceEditor/setBadges":
      return {
        ...state,
        workflowRun: {
          ...state.workflowRun,
          badges: resolveWorkflowRunUpdater(state.workflowRun.badges, action.badges),
        },
      };
    case "workspaceEditor/setTimestamps":
      return {
        ...state,
        workflowRun: {
          ...state.workflowRun,
          timestamps: resolveWorkflowRunUpdater(state.workflowRun.timestamps, action.timestamps),
        },
      };
    case "workspaceEditor/setWorkflowLogs":
      return {
        ...state,
        workflowRun: {
          ...state.workflowRun,
          workflowLogs: resolveWorkflowRunUpdater(
            state.workflowRun.workflowLogs,
            action.workflowLogs,
          ),
        },
      };
    case "workspaceEditor/setWorkflowParams":
      return {
        ...state,
        workflowRun: {
          ...state.workflowRun,
          workflowParams: resolveWorkflowRunUpdater(
            state.workflowRun.workflowParams,
            action.workflowParams,
          ),
        },
      };
    case "workspaceEditor/setToast":
      return {
        ...state,
        uiChrome: {
          ...state.uiChrome,
          toast: resolveUiChromeUpdater(state.uiChrome.toast, action.toast),
        },
      };
    case "workspaceEditor/setPage": {
      const candidate = resolveUiChromeUpdater(state.uiChrome.page, action.page);
      return {
        ...state,
        uiChrome: {
          ...state.uiChrome,
          page: normalizeUiChromePage(candidate, state.uiChrome.page),
        },
      };
    }
    case "workspaceEditor/setFocusedField":
      return {
        ...state,
        uiChrome: {
          ...state.uiChrome,
          focusedField: resolveUiChromeUpdater(state.uiChrome.focusedField, action.focusedField),
        },
      };
    case "workspaceEditor/setNavCollapsed":
      return {
        ...state,
        uiChrome: {
          ...state.uiChrome,
          navCollapsed: resolveUiChromeUpdater(state.uiChrome.navCollapsed, action.navCollapsed),
        },
      };
    case "workspaceEditor/setWorkspaceFiles":
      return {
        ...state,
        workspaceRemote: {
          ...state.workspaceRemote,
          workspaceFiles: resolveWorkspaceRemoteUpdater(
            state.workspaceRemote.workspaceFiles,
            action.workspaceFiles,
          ),
        },
      };
    case "workspaceEditor/setReeArtifactFiles":
      return {
        ...state,
        workspaceRemote: {
          ...state.workspaceRemote,
          reeArtifactFiles: resolveWorkspaceRemoteUpdater(
            state.workspaceRemote.reeArtifactFiles,
            action.reeArtifactFiles,
          ),
        },
      };
    case "workspaceEditor/hydrateWorkspace":
      return {
        ...state,
        workspaceDraft: {
          ...state.workspaceDraft,
          ree: action.workspace.ree
            ? enforceSourceOriginRules(action.workspace.ree)
            : state.workspaceDraft.ree,
        },
        workspaceRemote: {
          ...state.workspaceRemote,
          workspaceFiles: action.workspace.workspaceFiles,
          reeArtifactFiles: action.workspace.reeArtifactFiles,
        },
      };
    case "workspaceEditor/setSourceSnapshotFiles":
      return {
        ...state,
        workspaceRemote: {
          ...state.workspaceRemote,
          sourceSnapshotFiles: resolveWorkspaceRemoteUpdater(
            state.workspaceRemote.sourceSnapshotFiles,
            action.sourceSnapshotFiles,
          ),
        },
      };
    case "workspaceEditor/setSourceSnapshotArchiveName":
      return {
        ...state,
        workspaceRemote: {
          ...state.workspaceRemote,
          sourceSnapshotArchiveName: resolveWorkspaceRemoteUpdater(
            state.workspaceRemote.sourceSnapshotArchiveName,
            action.sourceSnapshotArchiveName,
          ),
        },
      };
    case "workspaceEditor/applySourcePatchOutcome":
      return {
        ...state,
        workspaceDraft: {
          ...state.workspaceDraft,
          ree: enforceSourceOriginRules({
            ...state.workspaceDraft.ree,
            ...action.outcome.reePatch,
          }),
        },
        workspaceRemote: {
          ...state.workspaceRemote,
          sourceSnapshotFiles: action.outcome.sourceSnapshotFiles,
          sourceSnapshotArchiveName: action.outcome.sourceSnapshotArchiveName,
        },
        workflowRun: {
          ...state.workflowRun,
          actionStates: action.outcome.actionState
            ? { ...state.workflowRun.actionStates, source: action.outcome.actionState }
            : state.workflowRun.actionStates,
          badges:
            typeof action.outcome.badge === "boolean"
              ? { ...state.workflowRun.badges, source: action.outcome.badge }
              : state.workflowRun.badges,
          timestamps: action.outcome.timestamp
            ? { ...state.workflowRun.timestamps, source: action.outcome.timestamp }
            : state.workflowRun.timestamps,
        },
      };
    case "workspaceEditor/setShowReviewPreview":
      return {
        ...state,
        uiChrome: {
          ...state.uiChrome,
          showReviewPreview: resolveUiChromeUpdater(
            state.uiChrome.showReviewPreview,
            action.showReviewPreview,
          ),
        },
      };
    case "workspaceEditor/completeWorkflowRun":
      return {
        ...state,
        workflowRun: {
          ...state.workflowRun,
          workflowLogs: {
            ...state.workflowRun.workflowLogs,
            [action.completion.key]: action.completion.workflowLog,
          },
          actionStates: {
            ...state.workflowRun.actionStates,
            [action.completion.key]: action.completion.actionState,
          },
          badges: {
            ...state.workflowRun.badges,
            [action.completion.key]: action.completion.badge,
          },
          timestamps: {
            ...state.workflowRun.timestamps,
            [action.completion.key]: action.completion.timestamp,
          },
        },
      };
    case "workspaceEditor/resetWorkflowOnSourceChange": {
      const resetState = computeSourceChangeConsequences(
        { ree: state.workspaceDraft.ree },
        action.workflowParams,
      );
      return {
        ...state,
        workspaceDraft: {
          ...state.workspaceDraft,
          ree: resetState.ree,
        },
        workspaceRemote: {
          ...state.workspaceRemote,
          workspaceFiles: resetState.workspaceFiles,
          reeArtifactFiles: resetState.reeArtifactFiles,
          sourceSnapshotFiles: resetState.sourceSnapshotFiles,
          sourceSnapshotArchiveName: resetState.sourceSnapshotArchiveName,
        },
        workflowRun: {
          ...state.workflowRun,
          actionStates: resetState.actionStates,
          badges: resetState.badges,
          timestamps: resetState.timestamps,
          workflowLogs: resetState.workflowLogs,
          workflowParams: resetState.workflowParams,
        },
      };
    }
    default:
      return state;
  }
}

export function WorkspaceEditorProvider({
  children,
  initialWorkspaceEditorRee,
}: WorkspaceEditorProviderProps) {
  const [state, dispatch] = useReducer(
    workspaceEditorReducer,
    initialWorkspaceEditorRee,
    createInitialState,
  );

  const value = useMemo(
    () => ({
      state,
      dispatch,
    }),
    [state],
  );

  return (
    <WorkspaceEditorContext.Provider value={value}>{children}</WorkspaceEditorContext.Provider>
  );
}

export function useWorkspaceEditorContext(): WorkspaceEditorContextValue {
  const ctx = useContext(WorkspaceEditorContext);
  if (!ctx) {
    throw new Error("useWorkspaceEditorContext must be used within WorkspaceEditorProvider");
  }
  return ctx;
}
