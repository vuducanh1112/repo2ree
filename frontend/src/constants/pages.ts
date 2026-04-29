import type { Ree } from "../types/reeModel";

// Workspace-editor pages.
export const PAGE = {
  SOURCE: "source",
  METADATA: "metadata",
  HBOM: "hbom",
  OVERVIEW: "overview",
  SEAL: "seal",
  ARCHIVE: "archive",
  FILES: "files",
  // Service pages — keys match Service.key values
  EVALUATE: "evaluate",
  BUILD: "build",
  SBOM: "sbom",
  ACTIVATION: "activation",
} as const;

export const APP_ROUTE = {
  ROOT: "/",
  EXPLORER: "/explorer",
  REVIEWER: "/reviewer",
} as const;

export type AppLoadRoutePath =
  | typeof APP_ROUTE.EXPLORER
  | typeof APP_ROUTE.REVIEWER
  | `${typeof APP_ROUTE.EXPLORER}?${string}`
  | `${typeof APP_ROUTE.REVIEWER}?${string}`;

export type WorkspaceEditorPage = (typeof PAGE)[keyof typeof PAGE];
const WORKSPACE_EDITOR_PAGES = Object.values(PAGE) as WorkspaceEditorPage[];
export type ExplorerPage = WorkspaceEditorPage;

// Maps a Ree field key to the workspace-editor page where it can be edited.
export const FIELD_TO_PAGE: Partial<Record<keyof Ree, WorkspaceEditorPage>> = {
  origin_url: PAGE.SOURCE,
  source_type: PAGE.SOURCE,
  _sourceAvailable: PAGE.SOURCE,
  _sourceAcquiredBy: PAGE.SOURCE,
  hardware_description: PAGE.HBOM,
  runtime: PAGE.BUILD,
  build_runtime_script: PAGE.BUILD,
  activation_script: PAGE.ACTIVATION,
  sbom: PAGE.SBOM,
  swhid: PAGE.ARCHIVE,
  zenodo_doi: PAGE.ARCHIVE,
  dataverse_doi: PAGE.ARCHIVE,
};

export function isValidWorkspaceEditorPage(value: string): value is WorkspaceEditorPage {
  return WORKSPACE_EDITOR_PAGES.includes(value as WorkspaceEditorPage);
}
