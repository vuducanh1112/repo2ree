import { type AppShellPage, FIELD_TO_PAGE, isValidAppShellPage, PAGE } from "./AppShellPages";

export function normalizeAppShellPage(
  candidate: string | null | undefined,
  fallback: AppShellPage = PAGE.OVERVIEW,
): AppShellPage {
  if (candidate && isValidAppShellPage(candidate)) {
    return candidate;
  }
  return fallback;
}

export function appShellPageForField(
  fieldKey: string,
  fallback: AppShellPage = PAGE.METADATA,
): AppShellPage {
  return FIELD_TO_PAGE[fieldKey as keyof typeof FIELD_TO_PAGE] ?? fallback;
}
