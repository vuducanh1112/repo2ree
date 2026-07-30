import type { ReeEditorViewModel } from "@core/ree-editor/reeEditorViewModel";

// Workspace shell pages.
export const PAGE = {
  WORKBENCH: "workbench",
  SOURCE: "source",
  METADATA: "metadata",
  EXPERIMENTS: "experiments",
  HBOM: "hbom",
  // The hub canvas itself: no dock is open, the pod and its nodes fill the view.
  CANVAS: "canvas",
  SEAL: "seal",
  ARCHIVE: "archive",
  // Step pages — keys match the runs API's operation keys.
  EVALUATE: "evaluate",
  BUILD: "build",
  SBOM: "sbom",
  ACTIVATION: "activation",
} as const;

export const APP_ROUTE = {
  ROOT: "/",
  WORKSPACE: "/workspace",
  AGENTS: "/agents",
  // The durable record of what this control plane has sealed. Not REE-scoped:
  // an entry outlives the workbench it was authored in.
  REE_INDEX: "/ree-index",
  // Lab-location picker: the first step of REE creation, where the user chooses
  // which agent hosts the workbench before the workbench/image page.
  LAB_LOCATION: "/lab-location",
} as const;

export type AppLoadRoutePath =
  | typeof APP_ROUTE.WORKSPACE
  | `${typeof APP_ROUTE.WORKSPACE}?${string}`
  | typeof APP_ROUTE.LAB_LOCATION
  | `${typeof APP_ROUTE.LAB_LOCATION}?${string}`;

// Carried from the landing screen through the lab-location picker to the
// workbench step: the user came to load an existing REE, not to start a blank
// one, so that step asks for the bundle before it will provision.
export const LOAD_REE_PARAM = "load";

export type AppShellPage = (typeof PAGE)[keyof typeof PAGE];
const WORKSPACE_SHELL_PAGES = Object.values(PAGE) as AppShellPage[];

// Maps a draft view-model field key to the app-shell page where it can be edited.
const FIELD_TO_PAGE: Partial<Record<keyof ReeEditorViewModel, AppShellPage>> = {
  originUrl: PAGE.SOURCE,
  sourceType: PAGE.SOURCE,
  experiments: PAGE.EXPERIMENTS,
  sourceAvailable: PAGE.SOURCE,
  sourceAcquiredBy: PAGE.SOURCE,
  hardwareDescription: PAGE.HBOM,
  runtime: PAGE.BUILD,
  activation: PAGE.ACTIVATION,
  sbom: PAGE.SBOM,
  swhid: PAGE.ARCHIVE,
};

function isValidAppShellPage(value: string): value is AppShellPage {
  return WORKSPACE_SHELL_PAGES.includes(value as AppShellPage);
}

export function normalizeAppShellPage(
  candidate: string | null | undefined,
  fallback: AppShellPage = PAGE.CANVAS,
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
