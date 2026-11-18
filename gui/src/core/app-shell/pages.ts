import { STEP } from "@core/generated/vocabulary";
import type { ReeSpec } from "@core/ree/ReeSpec";
import type { WorkspaceSourceState } from "@core/workspace/WorkspaceSourceState";

// Workspace shell pages.
// A page that does one of the REE's steps is keyed by that step.
export const PAGE = {
  WORKBENCH: "workbench",
  ACQUIRE_SOURCE: STEP.ACQUIRE_SOURCE,
  METADATA: STEP.METADATA,
  EXPERIMENTS: STEP.EXPERIMENTS,
  OBSERVE_HARDWARE: STEP.OBSERVE_HARDWARE,
  // The hub canvas itself: no dock is open, the pod and its nodes fill the view.
  CANVAS: "canvas",
  SEAL_REE: STEP.SEAL_REE,
  ARCHIVE: "archive",
  EVALUATE_REPRODUCIBILITY: STEP.EVALUATE_REPRODUCIBILITY,
  BUILD_EXPERIMENT_ENVIRONMENT: STEP.BUILD_EXPERIMENT_ENVIRONMENT,
  GENERATE_SBOM: STEP.GENERATE_SBOM,
  ACTIVATE_EXPERIMENT_ENVIRONMENT: STEP.ACTIVATE_EXPERIMENT_ENVIRONMENT,
} as const;

export const APP_ROUTE = {
  ROOT: "/",
  WORKSPACE: "/workspace",
  LABS: "/labs",
  // The durable record of what this control plane has sealed. Not REE-scoped:
  // an entry outlives the workbench it was authored in.
  REE_INDEX: "/ree-index",
  // Lab-location picker: the first step of REE creation, where the user chooses
  // which lab hosts the workbench before the workbench/image page.
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
type EditorField = keyof ReeSpec | keyof WorkspaceSourceState;

const FIELD_TO_PAGE: Partial<Record<EditorField, AppShellPage>> = {
  originUrl: PAGE.ACQUIRE_SOURCE,
  sourceType: PAGE.ACQUIRE_SOURCE,
  experiments: PAGE.EXPERIMENTS,
  sourceAvailable: PAGE.ACQUIRE_SOURCE,
  sourceAcquiredBy: PAGE.ACQUIRE_SOURCE,
  hbom: PAGE.OBSERVE_HARDWARE,
  experimentEnvironmentPath: PAGE.BUILD_EXPERIMENT_ENVIRONMENT,
  sbom: PAGE.GENERATE_SBOM,
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
  return FIELD_TO_PAGE[fieldKey as EditorField] ?? fallback;
}
