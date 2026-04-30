import {
  FIELD_TO_PAGE,
  isValidWorkspaceShellPage,
  PAGE,
  type WorkspaceShellPage,
} from "./WorkspaceShellPages";

export function normalizeWorkspaceShellPage(
  candidate: string | null | undefined,
  fallback: WorkspaceShellPage = PAGE.OVERVIEW,
): WorkspaceShellPage {
  if (candidate && isValidWorkspaceShellPage(candidate)) {
    return candidate;
  }
  return fallback;
}

export function workspaceShellPageForField(
  fieldKey: string,
  fallback: WorkspaceShellPage = PAGE.METADATA,
): WorkspaceShellPage {
  return FIELD_TO_PAGE[fieldKey as keyof typeof FIELD_TO_PAGE] ?? fallback;
}
