import { useReeEditor } from "@shell/state/ree-editor/hooks/useReeEditor";
import { useAppShellContext } from "../providers/AppShellProvider";

export function useAppShell() {
  const { state, dispatch } = useAppShellContext();
  const reeIntent = state.reeIntent;
  const stepRuns = state.stepRuns;
  const uiChrome = state.uiChrome;
  const reeEditor = useReeEditor({
    reeIntent,
    stepRuns,
    dispatch,
  });

  return {
    ...reeEditor,
    chrome: {
      ...uiChrome,
      // Immutability is a fact of the backend REE, never a reversible browser flag.
      locked: !!reeEditor.model.ree.artifact.sealedAt,
    },
  };
}
