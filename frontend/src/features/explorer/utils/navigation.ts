import { type ExplorerPage, FIELD_TO_PAGE, PAGE } from "../../../constants/pages";

export function explorerPageForField(
  fieldKey: string,
  fallback: ExplorerPage = PAGE.METADATA,
): ExplorerPage {
  return FIELD_TO_PAGE[fieldKey as keyof typeof FIELD_TO_PAGE] ?? fallback;
}
