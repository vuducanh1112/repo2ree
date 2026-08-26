import type { ArtifactStatus } from "../artifact/ArtifactStatus";
import type { EvaluationState } from "../evaluate/EvaluationState";
import { normalizeHBOM } from "../hbom/HbomSummary";
import type { WorkspaceSourceState } from "../workspace/WorkspaceSourceState";
import {
  createEmptyExperimentResourceEstimates,
  createEmptyReeActivation,
  createEmptyReeCatalogMetadata,
  createEmptyReeExperiment,
  type ReeActivation,
  type ReeCatalogMetadata,
  type ReeContributor,
  type ReeExperiment,
  type ReeRunnable,
  type ReeSpec,
} from "./ReeSpec";
import { mapRawStepEvidence, type StepEvidence } from "./StepEvidence";

// ================================================
// Types
// ================================================

interface MapRawReeIntentToReeOptions {
  reeIntent: Record<string, unknown> | null | undefined;
  reeSession?: Record<string, unknown> | null | undefined;
  /** The REE document's audit, as shipped: `StepAudit` per step. */
  audit?: unknown;
  fallbackName: string;
  fallbackOriginUrl?: string;
}

export interface RawReeIntentSlices {
  reeSpec: ReeSpec;
  workspaceSourceState: WorkspaceSourceState;
  artifactStatus: ArtifactStatus;
  evaluationState: EvaluationState;
  stepEvidence: StepEvidence;
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
          affiliationName: String(item.affiliation_name ?? ""),
          affiliationIdentifier: String(item.affiliation_identifier ?? ""),
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
    correspondingAuthorIdentifier: metadata.corresponding_author_identifier
      ? String(metadata.corresponding_author_identifier)
      : null,
  };
}

function mapRawResourceEstimates(value: unknown): ReeExperiment["resourceEstimates"] {
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

// Map the shared Runnable fields (description / runScript / verifyScript /
// outputPaths / estimates) common to experiments and activation. runScript
// falls back to defaultRunScript when absent, so activation can default to its
// reserved path.
function mapRawRunnable(raw: Record<string, unknown>, defaultRunScript = ""): ReeRunnable {
  return {
    description: String(raw.description ?? ""),
    runScript: raw.run_script ? String(raw.run_script) : defaultRunScript,
    verifyScript: raw.verify_script ? String(raw.verify_script) : "",
    outputPaths: Array.isArray(raw.output_paths)
      ? raw.output_paths.map((path) => String(path)).filter(Boolean)
      : [],
    runtimeEstimate: String(raw.runtime_estimate ?? ""),
    resourceEstimates: mapRawResourceEstimates(raw.resource_estimates),
  };
}

function mapRawActivation(value: unknown): ReeActivation {
  const raw = value && typeof value === "object" ? (value as Record<string, unknown>) : {};
  const activation = createEmptyReeActivation();
  return {
    ...activation,
    ...mapRawRunnable(raw, activation.runScript),
  };
}

// ================================================
// Mapper
// ================================================

export function mapRawReeIntentToSlices({
  reeIntent,
  reeSession,
  audit,
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
      catalogMetadata: mapRawCatalogMetadata(intent.catalog_metadata),
      originUrl: String(intent.origin_url ?? fallbackOriginUrl ?? ""),
      sourceType: (intent.source_type as ReeSpec["sourceType"]) || "",
      resolvedRevision: String(intent.revision ?? ""),
      runtime: String(intent.runtime ?? ""),
      activation: mapRawActivation(intent.activation),
      sbom: String(intent.sbom ?? ""),
      swhid: String(intent.swhid ?? ""),
      experiments,
      hardwareDescription: normalizeHBOM(intent.hardware_description),
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
    stepEvidence: mapRawStepEvidence(audit),
  };
}
