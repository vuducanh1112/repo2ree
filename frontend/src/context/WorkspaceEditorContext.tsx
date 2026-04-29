import type { ReactNode } from "react";
import { createContext, useContext, useMemo, useReducer } from "react";
import {
  applyWorkspaceEditorAction,
  createInitialWorkspaceEditorState,
} from "../application/workspace/workspaceEditorState";
import type { Ree } from "../types";
import type { WorkspaceEditorAction, WorkspaceEditorContextState } from "./workspaceEditorTypes";

interface WorkspaceEditorContextValue {
  state: WorkspaceEditorContextState;
  dispatch: React.Dispatch<WorkspaceEditorAction>;
}

const WorkspaceEditorContext = createContext<WorkspaceEditorContextValue | null>(null);

interface WorkspaceEditorProviderProps {
  children: ReactNode;
  initialExplorerRee: Ree;
}

function createInitialState(initialExplorerRee: Ree): WorkspaceEditorContextState {
  return {
    explorer: createInitialWorkspaceEditorState(initialExplorerRee),
  };
}

function workspaceEditorReducer(
  state: WorkspaceEditorContextState,
  action: WorkspaceEditorAction,
): WorkspaceEditorContextState {
  return {
    ...state,
    explorer: applyWorkspaceEditorAction(state.explorer, action),
  };
}

export function WorkspaceEditorProvider({
  children,
  initialExplorerRee,
}: WorkspaceEditorProviderProps) {
  const [state, dispatch] = useReducer(
    workspaceEditorReducer,
    initialExplorerRee,
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
