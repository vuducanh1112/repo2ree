import type { ReactNode } from "react";
import { createContext, useContext, useMemo, useReducer } from "react";
import type {
  AppShellAction,
  AppShellContextState,
} from "../../../application/app-shell/AppShellTypes";
import type { ArtifactStatus } from "../../../domain/artifact/ArtifactStatus";
import type { ReeSpec } from "../../../domain/ree/ReeSpec";
import type { EvaluationState } from "../../../domain/review/EvaluationState";
import type { WorkspaceSourceState } from "../../../domain/workspace/WorkspaceSourceState";
import { appShellReducer, createInitialState } from "./appShellReducer";

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

export { appShellReducer, createInitialState };

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
