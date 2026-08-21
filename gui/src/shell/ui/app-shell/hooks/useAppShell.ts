import { useReeEditor } from "@shell/state/ree-editor/hooks/useReeEditor";
import { useAppShellContext } from "../providers/AppShellProvider";

export function useAppShell() {
  const { state, dispatch } = useAppShellContext();
  const reeIntent = state.reeIntent;
  const reeSession = state.reeSession;
  const stepRuns = state.stepRuns;
  const uiChrome = state.uiChrome;
  const reeEditor = useReeEditor({
    reeIntent,
    reeSession,
    stepRuns,
    uiChrome,
    dispatch,
  });

  return {
    ...reeEditor,
    chrome: uiChrome,
  };
}
