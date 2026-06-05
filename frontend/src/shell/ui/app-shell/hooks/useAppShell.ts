import { useReeEditor } from "../../ree-editor/hooks/useReeEditor";
import { useAppShellContext } from "../providers/AppShellProvider";

export function useAppShell() {
  const { state, dispatch } = useAppShellContext();
  const reeIntent = state.reeIntent;
  const reeSession = state.reeSession;
  const assemblyRun = state.assemblyRun;
  const uiChrome = state.uiChrome;
  const reeEditor = useReeEditor({
    reeIntent,
    reeSession,
    assemblyRun,
    uiChrome,
    dispatch,
  });

  return {
    ...reeEditor,
    uiChrome,
  };
}
