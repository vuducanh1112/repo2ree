import type { ReeEditorViewModel } from "../../../../core/ree-editor/reeEditorViewModel";

// Workspace shell pages.
export const PAGE = {
  WORKBENCH: "workbench",
  SOURCE: "source",
  METADATA: "metadata",
  EXPERIMENTS: "experiments",
  HBOM: "hbom",
  OVERVIEW: "overview",
  SEAL: "seal",
  ARCHIVE: "archive",
  // Assembly pages — keys match assembly operation keys.
  EVALUATE: "evaluate",
  BUILD: "build",
  SBOM: "sbom",
  ACTIVATION: "activation",
} as const;

export const APP_ROUTE = {
  ROOT: "/",
  WORKSPACE: "/workspace",
  REVIEWER: "/reviewer",
} as const;

export type AppLoadRoutePath =
  | typeof APP_ROUTE.WORKSPACE
  | typeof APP_ROUTE.REVIEWER
  | `${typeof APP_ROUTE.WORKSPACE}?${string}`
  | `${typeof APP_ROUTE.REVIEWER}?${string}`;

export type AppShellPage = (typeof PAGE)[keyof typeof PAGE];
const WORKSPACE_SHELL_PAGES = Object.values(PAGE) as AppShellPage[];

// Maps a draft view-model field key to the app-shell page where it can be edited.
const FIELD_TO_PAGE: Partial<Record<keyof ReeEditorViewModel, AppShellPage>> = {
  origin_url: PAGE.SOURCE,
  source_type: PAGE.SOURCE,
  experiments: PAGE.EXPERIMENTS,
  sourceAvailable: PAGE.SOURCE,
  sourceAcquiredBy: PAGE.SOURCE,
  hardware_description: PAGE.HBOM,
  runtime: PAGE.BUILD,
  build_runtime_script: PAGE.BUILD,
  activation: PAGE.ACTIVATION,
  sbom: PAGE.SBOM,
  swhid: PAGE.ARCHIVE,
  zenodo_doi: PAGE.ARCHIVE,
  dataverse_doi: PAGE.ARCHIVE,
};

function isValidAppShellPage(value: string): value is AppShellPage {
  return WORKSPACE_SHELL_PAGES.includes(value as AppShellPage);
}

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
