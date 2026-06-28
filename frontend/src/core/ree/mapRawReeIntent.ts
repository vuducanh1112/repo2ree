import type { ArtifactStatus } from "../artifact/ArtifactStatus";
import type { EvaluationState } from "../evaluate/EvaluationState";
import { normalizeHBOM } from "../hbom/HbomSummary";
import type { WorkspaceSourceState } from "../workspace/WorkspaceSourceState";
import {
  createEmptyExperimentResourceEstimates,
  createEmptyReeActivation,
  createEmptyReeCatalogMetadata,
  createEmptyReeExperiment,
  type ExpectedOutput,
  type ReeActivation,
  type ReeCatalogMetadata,
  type ReeContributor,
  type ReeExperiment,
  type ReeSpec,
} from "./ReeSpec";

// ================================================
// Types
// ================================================

interface MapRawReeIntentToReeOptions {
  reeIntent: Record<string, unknown> | null | undefined;
  reeSession?: Record<string, unknown> | null | undefined;
  fallbackName: string;
  fallbackOriginUrl?: string;
}

export interface RawReeIntentSlices {
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

// Map the shared Runnable fields (description / run_script / estimates / outputs)
// common to experiments and activation. run_script falls back to defaultRunScript
// when absent, so activation can default to its reserved path.
function mapRawRunnable(
  raw: Record<string, unknown>,
  defaultRunScript = "",
): Omit<ReeExperiment, "name"> {
  return {
    description: String(raw.description ?? ""),
    run_script: raw.run_script ? String(raw.run_script) : defaultRunScript,
    runtime_estimate: String(raw.runtime_estimate ?? ""),
    resource_estimates: mapRawResourceEstimates(raw.resource_estimates),
    ...(Array.isArray(raw.outputs) && raw.outputs.length > 0
      ? { outputs: raw.outputs as ExpectedOutput[] }
      : {}),
  };
}

function mapRawActivation(value: unknown): ReeActivation {
  const raw = value && typeof value === "object" ? (value as Record<string, unknown>) : {};
  const activation = createEmptyReeActivation();
  return {
    ...activation,
    ...mapRawRunnable(raw, activation.run_script),
  };
}

// ================================================
// Mapper
// ================================================

export function mapRawReeIntentToSlices({
  reeIntent,
  reeSession,
  fallbackName,
  fallbackOriginUrl = "",
}: MapRawReeIntentToReeOptions): RawReeIntentSlices {
  const intent = reeIntent || {};
  const session = reeSession || {};

  const experiments: ReeExperiment[] = Array.isArray(intent.experiments)
    ? intent.experiments.map((entry) => {
        const item = (entry as Record<string, unknown>) || {};
        return {
          ...createEmptyReeExperiment(),
          name: String(item.name ?? ""),
          ...mapRawRunnable(item),
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
      activation: mapRawActivation(intent.activation),
      sbom: String(intent.sbom ?? ""),
      swhid: String(intent.swhid ?? ""),
      zenodo_doi: intent.zenodo_doi ? String(intent.zenodo_doi) : undefined,
      dataverse_doi: intent.dataverse_doi ? String(intent.dataverse_doi) : undefined,
      experiments,
      hardware_description: normalizeHBOM(intent.hardware_description),
    },
    workspaceSourceState: {
      sourceAvailable: Boolean(session.source_available),
      sourceIncluded: Boolean(session.source_included),
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
      runtimeIncluded: Boolean(session.runtime_included),
      sealedAt: session.sealed_at ? String(session.sealed_at) : undefined,
      sealHash: session.seal_hash ? String(session.seal_hash) : undefined,
    },
    evaluationState: {
      dependencyLevel: Number(session.dependency_level ?? 0),
      environmentLevel: Number(session.environment_level ?? 0),
      machineLevel: Number(session.machine_level ?? 0),
      detectedDependencies: session.detected_dependencies
        ? String(session.detected_dependencies)
        : undefined,
    },
  };
}
