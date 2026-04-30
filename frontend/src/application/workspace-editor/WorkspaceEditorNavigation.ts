import {
  FIELD_TO_PAGE,
  isValidWorkspaceEditorPage,
  PAGE,
  type WorkspaceEditorPage,
} from "./WorkspaceEditorPages";

export function normalizeWorkspaceEditorPage(
  candidate: string | null | undefined,
  fallback: WorkspaceEditorPage = PAGE.OVERVIEW,
): WorkspaceEditorPage {
  if (candidate && isValidWorkspaceEditorPage(candidate)) {
    return candidate;
  }
  return fallback;
}

export function workspaceEditorPageForField(
  fieldKey: string,
  fallback: WorkspaceEditorPage = PAGE.METADATA,
): WorkspaceEditorPage {
  return FIELD_TO_PAGE[fieldKey as keyof typeof FIELD_TO_PAGE] ?? fallback;
}
