import type { ReactNode } from "react";
import { createContext, useContext, useMemo, useReducer } from "react";
import type {
  AppShellAction,
  AppShellContextState,
} from "../../../application/app-shell/AppShellTypes";
import { createEmptyReeViewState, type ReeViewState } from "../../../domain/ree/ReeViewState";
import { appShellReducer, createInitialState } from "./appShellReducer";

interface AppShellContextValue {
  state: AppShellContextState;
  dispatch: React.Dispatch<AppShellAction>;
}

const AppShellContext = createContext<AppShellContextValue | null>(null);

interface AppShellProviderProps {
  children: ReactNode;
  initialRee?: ReeViewState;
}

export { appShellReducer, createInitialState };

export function AppShellProvider({ children, initialRee }: AppShellProviderProps) {
  const [state, dispatch] = useReducer(
    appShellReducer,
    initialRee ?? createEmptyReeViewState(),
    createInitialState,
  );

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
