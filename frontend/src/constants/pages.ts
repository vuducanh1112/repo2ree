import type { Ree } from "../types/ree";

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
} as const;

export const APP_ROUTE = {
  ROOT: "/",
  EXPLORER: "/explorer",
  REVIEWER: "/reviewer",
} as const;

export type AppLoadRoutePath =
  | typeof APP_ROUTE.EXPLORER
  | typeof APP_ROUTE.REVIEWER
  | `${typeof APP_ROUTE.EXPLORER}?${string}`;

export type ExplorerPage = (typeof PAGE)[keyof typeof PAGE];
const EXPLORER_PAGES = Object.values(PAGE) as ExplorerPage[];

// Maps a Ree field key to the Explorer page where it can be edited.
export const FIELD_TO_PAGE: Partial<Record<keyof Ree, ExplorerPage>> = {
  origin_url: PAGE.SOURCE,
  source_type: PAGE.SOURCE,
  _sourceAvailable: PAGE.SOURCE,
  _sourceAcquiredBy: PAGE.SOURCE,
  runtime: PAGE.BUILD,
  build_runtime_script: PAGE.BUILD,
  activation_script: PAGE.ACTIVATION,
  sbom: PAGE.SBOM,
  swhid: PAGE.ARCHIVE,
  zenodo_doi: PAGE.ARCHIVE,
  dataverse_doi: PAGE.ARCHIVE,
};

export function isValidExplorerPage(value: string): value is ExplorerPage {
  return EXPLORER_PAGES.includes(value as ExplorerPage);
}
