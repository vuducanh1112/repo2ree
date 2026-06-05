import type { ArtifactStatus } from "../artifact/ArtifactStatus";
import { normalizeHBOM } from "../hbom/HbomSummary";
import type { EvaluationState } from "../review/EvaluationState";
import type { WorkspaceSourceState } from "../workspace/WorkspaceSourceState";
import {
  createEmptyExperimentResourceEstimates,
  createEmptyReeCatalogMetadata,
  createEmptyReeExperiment,
  type ExpectedOutput,
  type ReeCatalogMetadata,
  type ReeContributor,
  type ReeExperiment,
  type ReeSpec,
} from "./ReeSpec";

// ================================================
// Types
// ================================================

interface MapRawReeDraftToReeOptions {
  reeIntent: Record<string, unknown> | null | undefined;
  reeSession?: Record<string, unknown> | null | undefined;
  fallbackName: string;
  fallbackOriginUrl?: string;
}

export interface RawReeDraftSlices {
  reeSpec: ReeSpec;
  workspaceSourceState: WorkspaceSourceState;
  artifactStatus: ArtifactStatus;
  evaluationState: EvaluationState;
}

// ================================================
// Helpers
// ================================================

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

function mapRawResourceEstimates(value: unknown): ReeExperiment["resource_estimates"] {
  const estimates = value && typeof value === "object" ? (value as Record<string, unknown>) : {};
  return {
    ...createEmptyExperimentResourceEstimates(),
    cpu: String(estimates.cpu ?? ""),
    memory: String(estimates.memory ?? ""),
    gpu: String(estimates.gpu ?? ""),
    storage: String(estimates.storage ?? ""),
    network: String(estimates.network ?? ""),
  };
}

// ================================================
// Mapper
// ================================================

export function mapRawReeDraftToSlices({
  reeIntent,
  reeSession,
  fallbackName,
  fallbackOriginUrl = "",
}: MapRawReeDraftToReeOptions): RawReeDraftSlices {
  const intent = reeIntent || {};
  const session = reeSession || {};
  const packaging =
    intent.packaging && typeof intent.packaging === "object"
      ? (intent.packaging as Record<string, unknown>)
      : {};

  const experiments: ReeExperiment[] = Array.isArray(intent.experiments)
    ? intent.experiments.map((entry) => {
        const item = (entry as Record<string, unknown>) || {};
        return {
          ...createEmptyReeExperiment(),
          name: String(item.name ?? ""),
          description: String(item.description ?? ""),
          command: String(item.command ?? ""),
          runtime_estimate: String(item.runtime_estimate ?? ""),
          resource_estimates: mapRawResourceEstimates(item.resource_estimates),
          ...(Array.isArray(item.outputs) && item.outputs.length > 0
            ? { outputs: item.outputs as ExpectedOutput[] }
            : {}),
        };
      })
    : [];

  return {
    reeSpec: {
      name: String(intent.name ?? fallbackName ?? ""),
      catalog_metadata: mapRawCatalogMetadata(intent.catalog_metadata),
      origin_url: String(intent.origin_url ?? fallbackOriginUrl ?? ""),
      source_type: (intent.source_type as ReeSpec["source_type"]) || "",
      runtime: String(intent.runtime ?? ""),
      build_runtime_script: String(intent.build_runtime_script ?? ""),
      activation_script: String(intent.activation_script ?? ""),
      sbom: String(intent.sbom ?? ""),
      swhid: String(intent.swhid ?? ""),
      zenodo_doi: intent.zenodo_doi ? String(intent.zenodo_doi) : undefined,
      dataverse_doi: intent.dataverse_doi ? String(intent.dataverse_doi) : undefined,
      detected_dependencies: intent.detected_dependencies
        ? String(intent.detected_dependencies)
        : undefined,
      experiments,
      hardware_description: normalizeHBOM(intent.hardware_description),
    },
    workspaceSourceState: {
      sourceAvailable: Boolean(session.source_available),
      sourceIncluded: Boolean(packaging.source_included ?? session.source_included),
      sourceAcquiredBy:
        (session.source_acquired_by as WorkspaceSourceState["sourceAcquiredBy"]) || undefined,
      uploadedArchive: session.uploaded_archive ? String(session.uploaded_archive) : undefined,
      sourceSnapshotArchive: session.source_snapshot_archive
        ? String(session.source_snapshot_archive)
        : undefined,
      sourceSnapshotCapturedAt: session.source_snapshot_captured_at
        ? String(session.source_snapshot_captured_at)
        : undefined,
    },
    artifactStatus: {
      runtimeIncluded: Boolean(packaging.runtime_included ?? session.runtime_included),
      downloadableFiles: Array.isArray(session.downloadable_files)
        ? session.downloadable_files.map((item) => String(item))
        : [],
      sealedAt: session.sealed_at ? String(session.sealed_at) : undefined,
      sealHash: session.seal_hash ? String(session.seal_hash) : undefined,
    },
    evaluationState: {
      dependencyLevel: Number(session.dependency_level ?? 0),
      environmentLevel: Number(session.environment_level ?? 0),
      machineLevel: Number(session.machine_level ?? 0),
    },
  };
}
