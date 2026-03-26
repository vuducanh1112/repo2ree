import type { AppPage, ExplorerPage } from "../types";

// Top-level app pages (App component).
export const APP_PAGE = {
  LANDING: "landing",
  EXPLORER: "explorer",
  REVIEWER: "reviewer",
} as const;

// Explorer-internal pages (Explorer component).
export const PAGE = {
  SOURCE: "source",
  METADATA: "metadata",
  OVERVIEW: "overview",
  SEAL: "seal",
  ARCHIVE: "archive",
  FILES: "files",
  // Service pages — keys match Service.key values
  EVALUATE: "evaluate",
  BUILD: "build",
  SBOM: "sbom",
  ACTIVATION: "activation",
  SWH: "swh",
} as const;

// Maps a Ree field key to the Explorer page where it can be edited.
export const FIELD_TO_PAGE: Record<string, ExplorerPage> = {
  origin_url: PAGE.SOURCE,
  source_type: PAGE.SOURCE,
  _sourceAvailable: PAGE.SOURCE,
  _sourceAcquiredBy: PAGE.SOURCE,
  runtime: PAGE.BUILD,
  build_runtime_script: PAGE.BUILD,
  activation_script: PAGE.ACTIVATION,
  sbom: PAGE.SBOM,
  swhid: PAGE.SWH,
  zenodo_doi: PAGE.ARCHIVE,
  dataverse_doi: PAGE.ARCHIVE,
};

// Type guard to ensure only valid page names are used
export function isValidAppPage(value: string): value is AppPage {
  return Object.values(APP_PAGE).includes(value as AppPage);
}

export function isValidExplorerPage(value: string): value is ExplorerPage {
  return Object.values(PAGE).includes(value as ExplorerPage);
}
