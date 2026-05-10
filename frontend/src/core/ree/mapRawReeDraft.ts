import type { ArtifactStatus } from "../artifact/ArtifactStatus";
import { normalizeHBOM } from "../hbom/HbomSummary";
import type { EvaluationState } from "../review/EvaluationState";
import type { WorkspaceSourceState } from "../workspace/WorkspaceSourceState";
import {
  createEmptyReeCatalogMetadata,
  type ReeCatalogMetadata,
  type ReeContributor,
  type ReeExperiment,
  type ReeSpec,
} from "./ReeSpec";

interface MapRawReeDraftToReeOptions {
  reeDraft: Record<string, unknown> | null | undefined;
  fallbackName: string;
  fallbackOriginUrl?: string;
}

export interface RawReeDraftSlices {
  reeSpec: ReeSpec;
  workspaceSourceState: WorkspaceSourceState;
  artifactStatus: ArtifactStatus;
  evaluationState: EvaluationState;
}

function mapRawCatalogMetadata(value: unknown): ReeCatalogMetadata {
  const metadata = value && typeof value === "object" ? (value as Record<string, unknown>) : {};

  const contributors: ReeContributor[] = Array.isArray(metadata.contributors)
    ? metadata.contributors.map((entry) => {
        const item = (entry as Record<string, unknown>) || {};
        return {
          identifier: String(item.identifier ?? ""),
          name: String(item.name ?? ""),
          affiliation_name: String(item.affiliation_name ?? ""),
          affiliation_identifier: String(item.affiliation_identifier ?? ""),
        };
      })
    : [];

  return {
    ...createEmptyReeCatalogMetadata(),
    description: String(metadata.description ?? ""),
    version: String(metadata.version ?? ""),
    website: String(metadata.website ?? ""),
    keywords: Array.isArray(metadata.keywords)
      ? metadata.keywords.map((keyword) => String(keyword))
      : [],
    contributors,
    corresponding_author_identifier: metadata.corresponding_author_identifier
      ? String(metadata.corresponding_author_identifier)
      : null,
  };
}

export function mapRawReeDraftToSlices({
  reeDraft,
  fallbackName,
  fallbackOriginUrl = "",
}: MapRawReeDraftToReeOptions): RawReeDraftSlices {
  const draft = reeDraft || {};
  const experiments: ReeExperiment[] = Array.isArray(draft.experiments)
    ? draft.experiments.map((entry) => {
        const item = (entry as Record<string, unknown>) || {};
        return {
          name: String(item.name ?? ""),
          description: String(item.description ?? ""),
          command: String(item.command ?? ""),
        };
      })
    : [];

  return {
    reeSpec: {
      name: String(draft.name ?? fallbackName ?? ""),
      catalog_metadata: mapRawCatalogMetadata(draft.catalog_metadata),
      origin_url: String(draft.origin_url ?? fallbackOriginUrl ?? ""),
      source_type: (draft.source_type as ReeSpec["source_type"]) || "",
      runtime: String(draft.runtime ?? ""),
      build_runtime_script: String(draft.build_runtime_script ?? ""),
      activation_script: String(draft.activation_script ?? ""),
      sbom: String(draft.sbom ?? ""),
      swhid: String(draft.swhid ?? ""),
      zenodo_doi: draft.zenodo_doi ? String(draft.zenodo_doi) : undefined,
      dataverse_doi: draft.dataverse_doi ? String(draft.dataverse_doi) : undefined,
      repro_level: draft.repro_level ? String(draft.repro_level) : undefined,
      detected_dependencies: draft.detected_dependencies
        ? String(draft.detected_dependencies)
        : undefined,
      experiments,
      hardware_description: normalizeHBOM(draft.hardware_description),
    },
    workspaceSourceState: {
      sourceAvailable: Boolean(draft._sourceAvailable),
      sourceIncluded: Boolean(draft._sourceIncluded),
      sourceAcquiredBy:
        (draft._sourceAcquiredBy as WorkspaceSourceState["sourceAcquiredBy"]) || undefined,
      uploadedArchive: draft._uploadedArchive ? String(draft._uploadedArchive) : undefined,
      sourceSnapshotArchive: draft._sourceSnapshotArchive
        ? String(draft._sourceSnapshotArchive)
        : undefined,
      sourceSnapshotCapturedAt: draft._sourceSnapshotCapturedAt
        ? String(draft._sourceSnapshotCapturedAt)
        : undefined,
    },
    artifactStatus: {
      runtimeIncluded: Boolean(draft._runtimeIncluded),
      downloadableFiles: Array.isArray(draft._downloadableFiles)
        ? draft._downloadableFiles.map((item) => String(item))
        : [],
      sealedAt: draft._sealedAt ? String(draft._sealedAt) : undefined,
      sealHash: draft._sealHash ? String(draft._sealHash) : undefined,
    },
    evaluationState: {
      evalLevel: Number(draft._evalLevel ?? 0),
    },
  };
}
