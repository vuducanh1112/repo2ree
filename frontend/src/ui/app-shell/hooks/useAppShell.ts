import { useReeEditor } from "../../ree-editor/hooks/useReeEditor";
import { useAppShellContext } from "../providers/AppShellProvider";

export function useAppShell() {
  const { state, dispatch } = useAppShellContext();
  const reeDraft = state.reeDraft;
  const workflowRun = state.workflowRun;
  const uiChrome = state.uiChrome;
  const reeEditor = useReeEditor({
    reeDraft,
    workflowRun,
    uiChrome,
    dispatch,
  });

  return {
    ...reeEditor,
    uiChrome,
  };
}
