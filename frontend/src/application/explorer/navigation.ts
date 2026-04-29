import { type ExplorerPage, isValidExplorerPage, PAGE } from "../../constants/pages";

export function normalizeExplorerPage(
  candidate: string | null | undefined,
  fallback: ExplorerPage = PAGE.OVERVIEW,
): ExplorerPage {
  if (candidate && isValidExplorerPage(candidate)) {
    return candidate;
  }
  return fallback;
}
