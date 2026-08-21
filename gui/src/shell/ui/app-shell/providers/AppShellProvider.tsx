import type { ArtifactStatus } from "@core/artifact/ArtifactStatus";
import type { EvaluationState } from "@core/evaluate/EvaluationState";
import type { ReeSpec } from "@core/ree/ReeSpec";
import type { WorkspaceSourceState } from "@core/workspace/WorkspaceSourceState";
import { appShellReducer, createInitialState } from "@shell/state/ree-editor/store/appShellReducer";
import type { AppShellAction, AppShellContextState } from "@shell/state/ree-editor/store/types";
import type { ReactNode } from "react";
import { createContext, useContext, useMemo, useReducer } from "react";

interface AppShellContextValue {
  state: AppShellContextState;
  dispatch: React.Dispatch<AppShellAction>;
}

const AppShellContext = createContext<AppShellContextValue | null>(null);

interface AppShellProviderProps {
  children: ReactNode;
  initialState?: {
    reeSpec?: ReeSpec;
    workspaceSourceState?: WorkspaceSourceState;
    artifactStatus?: ArtifactStatus;
    evaluationState?: EvaluationState;
  };
}

export function AppShellProvider({ children, initialState }: AppShellProviderProps) {
  const [state, dispatch] = useReducer(appShellReducer, initialState ?? {}, createInitialState);

  const value = useMemo(
    () => ({
      state,
      dispatch,
    }),
    [state],
  );

  return <AppShellContext.Provider value={value}>{children}</AppShellContext.Provider>;
}

export function useAppShellContext(): AppShellContextValue {
  const ctx = useContext(AppShellContext);
  if (!ctx) {
    throw new Error("useAppShellContext must be used within AppShellProvider");
  }
  return ctx;
}
