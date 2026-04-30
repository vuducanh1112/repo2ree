import type { ReactNode } from "react";
import { createContext, useContext, useMemo, useReducer } from "react";
import {
  applyWorkspaceEditorAction,
  createInitialWorkspaceEditorState,
} from "../../../application/workspace-editor/WorkspaceEditorState";
import type {
  WorkspaceEditorAction,
  WorkspaceEditorContextState,
} from "../../../application/workspace-editor/WorkspaceEditorTypes";
import type { Ree } from "../../../domain/ree/ReeSpec";

interface WorkspaceEditorContextValue {
  state: WorkspaceEditorContextState;
  dispatch: React.Dispatch<WorkspaceEditorAction>;
}

const WorkspaceEditorContext = createContext<WorkspaceEditorContextValue | null>(null);

interface WorkspaceEditorProviderProps {
  children: ReactNode;
  initialWorkspaceEditorRee: Ree;
}

function createInitialState(initialWorkspaceEditorRee: Ree): WorkspaceEditorContextState {
  return {
    workspaceEditor: createInitialWorkspaceEditorState(initialWorkspaceEditorRee),
  };
}

function workspaceEditorReducer(
  state: WorkspaceEditorContextState,
  action: WorkspaceEditorAction,
): WorkspaceEditorContextState {
  return {
    ...state,
    workspaceEditor: applyWorkspaceEditorAction(state.workspaceEditor, action),
  };
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
