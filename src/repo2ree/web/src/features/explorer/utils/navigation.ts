import {
  type ExplorerPage,
  FIELD_TO_PAGE,
  isValidExplorerPage,
  PAGE,
} from "../../../constants/pages";

export function explorerPageForField(
  fieldKey: string,
  fallback: ExplorerPage = PAGE.METADATA,
): ExplorerPage {
  return FIELD_TO_PAGE[fieldKey as keyof typeof FIELD_TO_PAGE] ?? fallback;
}

export function normalizeExplorerPage(
  candidate: string | null | undefined,
  fallback: ExplorerPage = PAGE.OVERVIEW,
): ExplorerPage {
  if (candidate && isValidExplorerPage(candidate)) {
    return candidate;
  }
  return fallback;
}
