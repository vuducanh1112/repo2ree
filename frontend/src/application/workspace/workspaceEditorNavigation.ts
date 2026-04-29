import { isValidWorkspaceEditorPage, PAGE, type WorkspaceEditorPage } from "../../constants/pages";

export function normalizeWorkspaceEditorPage(
  candidate: string | null | undefined,
  fallback: WorkspaceEditorPage = PAGE.OVERVIEW,
): WorkspaceEditorPage {
  if (candidate && isValidWorkspaceEditorPage(candidate)) {
    return candidate;
  }
  return fallback;
}
