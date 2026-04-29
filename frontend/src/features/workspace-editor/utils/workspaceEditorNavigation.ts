import { FIELD_TO_PAGE, PAGE, type WorkspaceEditorPage } from "../../../constants/pages";

export function workspaceEditorPageForField(
  fieldKey: string,
  fallback: WorkspaceEditorPage = PAGE.METADATA,
): WorkspaceEditorPage {
  return FIELD_TO_PAGE[fieldKey as keyof typeof FIELD_TO_PAGE] ?? fallback;
}
